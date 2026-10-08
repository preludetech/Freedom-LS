"""Views for course_applications."""

from __future__ import annotations

from typing import cast
from urllib.parse import urlencode
from uuid import UUID

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.sites.models import Site
from django.db import transaction
from django.db.models import prefetch_related_objects
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from freedom_ls.accounts.decorators import never_cache_same_origin
from freedom_ls.accounts.legal_docs import has_legal_doc
from freedom_ls.accounts.models import User
from freedom_ls.accounts.utils import acquisition_auth_url, redirect_to_auth
from freedom_ls.content_engine.models import Course, CourseVisibility
from freedom_ls.course_access.analytics_events import record_application_submitted
from freedom_ls.course_access.visibility import raise_404_if_hidden_unregistered
from freedom_ls.course_applications.claims import (
    CLAIM_REPORT_SESSION_KEY,
    ClaimReport,
    claim_unclaimed_applications,
    remember_unclaimed_application,
    unclaimed_application_for_course,
    unclaimed_application_ids,
)
from freedom_ls.course_applications.forms import ApplicantEmailForm
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.course_applications.queries import get_application_for_course
from freedom_ls.form_engine.anonymous_sittings import (
    owned_or_held_q,
    remember_anonymous_sitting,
)
from freedom_ls.form_engine.enums import QuestionType
from freedom_ls.form_engine.models import Form, FormProgress, QuestionAnswer
from freedom_ls.form_engine.page_flow import (
    PageSubmission,
    page_at,
    page_context,
    render_form_page,
    resolve_page,
    submit_page,
)
from freedom_ls.form_engine.paging import (
    resume_page_number,
    unanswered_required_in_form,
    unanswered_required_message,
)
from freedom_ls.form_engine.queries import page_questions
from freedom_ls.site_aware_models.models import get_cached_site


def _start_application(user: User, course: Course) -> CourseApplication:
    """The applicant's application to this course, created if they have none.

    A course that names an application form gets a sitting of that form created
    alongside the application; the sitting is a draft, not a submission.

    Never called with a null user: `get_or_create(user=None, ...)` would match a
    stranger's draft.
    """
    with transaction.atomic():
        # get_or_create is race-safe (savepoint + IntegrityError catch +
        # re-get), so concurrent requests that both pass the existing-application
        # check still converge on one row.
        app: CourseApplication
        app, _ = CourseApplication.objects.get_or_create(
            user=user, course=course, defaults={"email": user.email}
        )
        if course.application_form is not None and app.form_progress is None:
            app.form_progress = FormProgress.objects.create(
                user=user, form=course.application_form
            )
            app.save(update_fields=["form_progress"])
    return app


@never_cache_same_origin
def apply(request: HttpRequest, course_slug: str) -> HttpResponse:
    """Apply entry view.

    A learner who already has an application is sent to its status page.

    A course that names an application form has nothing to confirm here: the
    application is not sent until the check-your-answers page. So any request,
    GET included, starts the application and its draft sitting and lands on the
    first form page. The course detail CTA is a plain link, so GET is the only
    request that link can make; starting twice converges on the same row.

    A course that names no form keeps the confirmation page, because there
    creating the application is the submission itself:
    GET: show confirmation page ("Apply to <course>?").
    POST: get_or_create the application, then redirect to status page.

    NOTE: when application review lands, the POST body will wrap get_or_create in
      an atomic block and call app.submit() (the FSM transition) + create an
      ApplicationStateTransition audit row.
    """
    if not request.user.is_authenticated and acquisition_auth_url(request) is None:
        # Signups closed: send to login before any course lookup, so a closed
        # site reveals nothing about which slugs exist.
        return redirect_to_auth(request, next_url=request.get_full_path())
    course = get_object_or_404(Course, slug=course_slug)
    # Enforce course visibility: hidden courses 404 for unregistered users.
    raise_404_if_hidden_unregistered(request.user, course)
    if not request.user.is_authenticated:
        return _apply_anonymous(request, course)
    user = cast(User, request.user)

    # An existing applicant always reaches their application record, even if the
    # course was later flipped to coming-soon — so this short-circuit precedes the
    # coming-soon redirect below.
    existing_app = get_application_for_course(user=user, course=course)
    if existing_app is not None:
        return redirect("course_applications:status", pk=existing_app.pk)

    # Coming-soon courses are not enrollable — route to the detail page's
    # express-interest CTA instead of creating an application.
    if course.visibility == CourseVisibility.COMING_SOON:
        return redirect("learner_interface:course_detail", course_slug=course.slug)

    if course.application_form is not None or request.method == "POST":
        app = _start_application(user, course)
        if app.form_progress is not None:
            return redirect(_resume_url(app, app.form_progress))
        record_application_submitted(request, course)
        return redirect("course_applications:status", pk=app.pk)

    return render(
        request,
        "course_applications/apply.html",
        {
            "course": course,
            "show_email_form": False,
            "email_form": None,
            "privacy_url": None,
        },
    )


def _privacy_url(request: HttpRequest) -> str | None:
    site = get_cached_site(request)
    if isinstance(site, Site) and has_legal_doc(site, "privacy"):
        return reverse("accounts:legal_doc", kwargs={"doc_type": "privacy"})
    return None


def _apply_anonymous(request: HttpRequest, course: Course) -> HttpResponse:
    held = unclaimed_application_for_course(request, course)
    if held is not None:
        if held.is_submitted:
            return _redirect_to_handoff(request, held)
        if held.form_progress is None:
            raise Http404
        return redirect(_resume_url(held, held.form_progress))
    if course.visibility == CourseVisibility.COMING_SOON:
        return redirect("learner_interface:course_detail", course_slug=course.slug)
    if course.application_form is not None:
        return _apply_anonymous_form_course(request, course)
    return _apply_anonymous_no_form_course(request, course)


def _session_days() -> int:
    """How many whole days a browser session, and so an unclaimed draft, lasts."""
    return int(settings.SESSION_COOKIE_AGE) // 86400


def _apply_anonymous_form_course(request: HttpRequest, course: Course) -> HttpResponse:
    """Page 1 of the form with no rows behind it, until the first valid save.

    Nothing is created for a visitor who only looks. The first page-1 POST
    that validates creates the unclaimed application and its sitting and saves
    the page; one that fails creates nothing.
    """
    form = course.application_form
    current = page_at(form, 1) if form is not None else None
    if form is None or current is None:
        # A form with no pages has no page 1 to show an anonymous visitor.
        raise Http404
    submission = PageSubmission()
    answers: dict[UUID, QuestionAnswer] = {}
    if request.method == "POST":
        with transaction.atomic():
            form_progress = FormProgress.objects.create(user=None, form=form)
            app = CourseApplication.objects.create(
                course=course, email="", form_progress=form_progress
            )
            submission = submit_page(
                current, request.POST, form_progress, ignore_file_questions=True
            )
            if not submission.accepted:
                # The rows exist only so the page could be checked. They are
                # rolled back, but what was typed is read first so the refused
                # page is drawn over those answers rather than over blanks.
                answers = form_progress.existing_answers_dict(current.questions)
                prefetch_related_objects(list(answers.values()), "selected_options")
                transaction.set_rollback(True)
        if submission.accepted:
            remember_anonymous_sitting(request, form_progress)
            remember_unclaimed_application(request, app)
            if any(
                question.type == QuestionType.FILE_UPLOAD
                for question in current.questions
            ):
                return redirect(f"{_page_url(app, 1)}?{SAVED_FOR_FILE}=1")
            if current.is_last:
                return redirect("course_applications:check_answers", pk=app.pk)
            return redirect(_page_url(app, 2))
    context = page_context(
        form, current, None, submission, lambda number: request.path, answers=answers
    ) | {
        "application": None,
        "course": course,
        "return_to_check": False,
        "check_answers_url": "",
        "is_unclaimed": True,
        "session_days": _session_days(),
    }
    return render_form_page(
        request, "course_applications/form_page.html", context, submission
    )


def _apply_anonymous_no_form_course(
    request: HttpRequest, course: Course
) -> HttpResponse:
    email_form = ApplicantEmailForm(request.POST or None)
    if request.method == "POST" and email_form.is_valid():
        app = CourseApplication.objects.create(
            course=course, email=email_form.cleaned_data["email"]
        )
        record_application_submitted(request, course)
        remember_unclaimed_application(request, app)
        return _redirect_to_handoff(request, app)
    return render(
        request,
        "course_applications/apply.html",
        {
            "course": course,
            "email_form": email_form,
            "show_email_form": True,
            "privacy_url": _privacy_url(request),
        },
        status=422 if request.method == "POST" else 200,
    )


def _redirect_to_handoff(request: HttpRequest, app: CourseApplication) -> HttpResponse:
    """Send an anonymous applicant to create or enter the account that will own this application.

    The typed address prefills signup. The response is the same for a
    registered and an unregistered address: nothing here looks an account up.
    """
    messages.success(
        request,
        f"Your application for {app.course.title} has been sent. "
        f"Create an account or log in with {app.email} to see its progress.",
    )
    auth_url = acquisition_auth_url(request)
    if auth_url is not None:
        auth_url = f"{auth_url}?{urlencode({'email': app.email})}"
    return redirect_to_auth(
        request, next_url=reverse("course_applications:claim"), auth_url=auth_url
    )


def _landing_for(app: CourseApplication) -> HttpResponse:
    if app.form_progress is not None and app.form_progress.completed_time is None:
        return redirect(_resume_url(app, app.form_progress))
    return redirect("course_applications:status", pk=app.pk)


@login_required
@require_GET
@never_cache_same_origin
def claim_landing(request: HttpRequest) -> HttpResponse:
    """Attach this browser's applications to the signed-in account and say what happened.

    Runs the claim again, so a visitor who has since verified the typed
    address can retry from the mismatch page. The report of any earlier run,
    such as the login receiver's, is shown once and then cleared.
    """
    claim_unclaimed_applications(request, cast(User, request.user))
    report = ClaimReport.from_session(
        request.session.pop(CLAIM_REPORT_SESSION_KEY, None)
    )
    claimed = list(
        CourseApplication.objects.filter(pk__in=report.claimed).select_related(
            "course", "form_progress__form"
        )
    )
    for app in claimed:
        messages.success(
            request,
            f"Your application for {app.course.title} is now on your dashboard.",
        )
    collided = (
        CourseApplication.objects.filter(pk__in=report.collided)
        .select_related("course")
        .first()
    )
    if collided is not None:
        messages.info(
            request,
            f"You had already applied to {collided.course.title}. This is your application.",
        )
    mismatched = (
        CourseApplication.objects.filter(pk__in=report.mismatched)
        .select_related("course")
        .first()
    )
    if mismatched is not None:
        return render(
            request,
            "course_applications/claim_mismatch.html",
            {"application": mismatched, "course": mismatched.course},
        )
    if len(claimed) == 1:
        return _landing_for(claimed[0])
    if claimed:
        return redirect("learner_interface:dashboard")
    if collided is not None:
        return redirect("course_applications:status", pk=collided.pk)
    messages.info(request, "We couldn't find an application in this browser.")
    return redirect("learner_interface:dashboard")


@login_required
def application_status(request: HttpRequest, pk: UUID) -> HttpResponse:
    """Applicant status page.

    Shows a static plain-language "received and pending review" confirmation.
    Only the application owner may view this page — non-owners get 404.

    An application whose form is still unfinished is sent back to it: there is
    nothing to say about a request that has not been made yet.

    NOTE: when application review lands, dynamic state rendering (state badge,
      reviewer message, withdraw action via get_available_user_state_transitions)
      goes here.
    """
    app = get_object_or_404(
        CourseApplication.objects.select_related("course", "form_progress"),
        pk=pk,
        user=request.user,
    )
    if app.form_progress is not None and app.form_progress.completed_time is None:
        return redirect(_resume_url(app, app.form_progress))
    return render(
        request,
        "course_applications/application_status.html",
        {"application": app},
    )


def _application_for_request(
    request: HttpRequest, pk: UUID
) -> tuple[CourseApplication, Form, FormProgress]:
    """The application this request may read and write, and its sitting, or 404.

    The requester's own application, or an unclaimed one whose id the session
    holds. Nothing else: a wrong, foreign, claimed or missing id is a plain
    404. A signed-in account still reaches a session-held unclaimed
    application, because until it is claimed the session is what created it.
    """
    allowed = owned_or_held_q(
        request,
        user_path="user",
        pk_path="pk",
        held_ids=unclaimed_application_ids(request),
    )
    app: CourseApplication = get_object_or_404(
        CourseApplication.objects.select_related(
            "course", "form_progress__form"
        ).filter(allowed),
        pk=pk,
    )
    if app.form_progress is None:
        raise Http404
    return app, app.form_progress.form, app.form_progress


def _page_url(app: CourseApplication, page_number: int) -> str:
    return reverse(
        "course_applications:form_page",
        kwargs={"pk": app.pk, "page_number": page_number},
    )


def _resume_url(app: CourseApplication, form_progress: FormProgress) -> str:
    """Where an unfinished sitting picks back up.

    A form with no pages has nothing to fill in, so the only place left to send
    the applicant is the page they submit from.
    """
    if not form_progress.form.pages.exists():
        return reverse("course_applications:check_answers", kwargs={"pk": app.pk})
    return _page_url(app, resume_page_number(form_progress))


# Query-string marker an Edit link from the check-your-answers page carries. A
# page reached with it saves and goes straight back there instead of advancing.
RETURN_TO_CHECK = "check"

# Marker the first save of a page with a file question carries back to that
# page, so it can say the file can now be attached.
SAVED_FOR_FILE = "saved"


@never_cache_same_origin
def application_form_page(
    request: HttpRequest, pk: UUID, page_number: int
) -> HttpResponse:
    """One page of the application form.

    A submitted application is read-only: its pages still render, so the
    applicant can re-read what they said, but nothing more is written to it.
    """
    app, form, form_progress = _application_for_request(request, pk)
    current = resolve_page(form, page_number)
    read_only = form_progress.completed_time is not None
    # The page form posts to its own URL, query string included, so the marker
    # survives both the save and a 422 re-render.
    return_to_check = request.GET.get("return") == RETURN_TO_CHECK

    def url_for_page(number: int) -> str:
        return _page_url(app, number)

    submission = PageSubmission()
    if request.method == "POST":
        if read_only:
            return _redirect_after_submission(request, app)
        submission = submit_page(current, request.POST, form_progress)
        if submission.accepted:
            if not current.is_last and not return_to_check:
                return redirect(url_for_page(page_number + 1))
            return redirect("course_applications:check_answers", pk=app.pk)

    if not read_only:
        form_progress.record_page_reached(page_number)
    context = page_context(
        form, current, form_progress, submission, url_for_page, read_only=read_only
    ) | {
        "application": app,
        "course": app.course,
        "return_to_check": return_to_check,
        "check_answers_url": reverse(
            "course_applications:check_answers", kwargs={"pk": app.pk}
        ),
        "saved_for_file": request.GET.get(SAVED_FOR_FILE) == "1",
        "is_unclaimed": not app.is_claimed,
        "session_days": _session_days(),
    }
    return render_form_page(
        request, "course_applications/form_page.html", context, submission
    )


def _redirect_after_submission(
    request: HttpRequest, app: CourseApplication
) -> HttpResponse:
    """Where a submitted application goes next: the status page once it has an owner.

    The status page is for the owner, so an unclaimed application re-enters the
    handoff instead.
    """
    if app.is_claimed:
        return redirect("course_applications:status", pk=app.pk)
    return _redirect_to_handoff(request, app)


@never_cache_same_origin
def application_check_answers(request: HttpRequest, pk: UUID) -> HttpResponse:
    """Everything the applicant has said, one card per page, and the one place
    they submit from.

    The whole-form check is what catches a required question on a page they
    never visited -- the per-page check cannot see those.
    """
    app, form, form_progress = _application_for_request(request, pk)
    submitted = form_progress.completed_time is not None
    required_answers_error = ""
    email_form = ApplicantEmailForm(request.POST if request.method == "POST" else None)
    refused = False

    if request.method == "POST" and not submitted:
        unanswered = unanswered_required_in_form(form_progress)
        if unanswered:
            required_answers_error = unanswered_required_message(unanswered)
            refused = True
        elif app.is_claimed:
            form_progress.complete()
            record_application_submitted(request, app.course)
            messages.success(
                request,
                f"Your application for {app.course.title} has been submitted "
                "and is pending review.",
            )
            return redirect("learner_interface:dashboard")
        elif email_form.is_valid():
            with transaction.atomic():
                form_progress.complete()
                app.email = email_form.cleaned_data["email"]
                app.save(update_fields=["email", "updated_at"])
            record_application_submitted(request, app.course)
            return _redirect_to_handoff(request, app)
        else:
            refused = True
    elif request.method == "POST":
        return _redirect_after_submission(request, app)

    # Fills the answers cache once; existing_answers_dict then reads from it, so
    # the loop below makes no per-row queries.
    prefetch_related_objects(
        [form_progress], "answers__selected_options", "answers__answer_file"
    )
    sections = []
    for number, page in enumerate(form.pages.all(), start=1):
        questions = page_questions(page)
        answers = form_progress.existing_answers_dict(questions)
        sections.append(
            {
                "title": page.title,
                "number": number,
                "edit_url": f"{_page_url(app, number)}?return={RETURN_TO_CHECK}",
                "rows": [
                    {"question": question, "answer": answers.get(question.id)}
                    for question in questions
                ],
            }
        )

    return render(
        request,
        "course_applications/check_your_answers.html",
        {
            "application": app,
            "course": app.course,
            "sections": sections,
            "submitted": submitted,
            "required_answers_error": required_answers_error,
            "email_form": email_form,
            "privacy_url": _privacy_url(request),
            "show_email_form": not app.is_claimed,
            "is_unclaimed": not app.is_claimed,
            "session_days": _session_days(),
        },
        status=422 if refused else 200,
    )
