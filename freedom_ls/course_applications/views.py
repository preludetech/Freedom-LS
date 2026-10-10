"""Views for course_applications."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
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
from freedom_ls.accounts.throttling import is_ip_throttled
from freedom_ls.accounts.utils import (
    acquisition_auth_url,
    get_effective_require_name,
    get_signup_policy_for_request,
    redirect_to_auth,
)
from freedom_ls.content_engine.models import Course, CourseVisibility
from freedom_ls.course_access.analytics_events import record_application_submitted
from freedom_ls.course_access.visibility import raise_404_if_hidden_unregistered
from freedom_ls.course_applications.claims import (
    CLAIM_REPORT_SESSION_KEY,
    ClaimReport,
    claim_unclaimed_applications,
    has_unverified_address,
    remember_unclaimed_application,
    unclaimed_application_for_course,
    unclaimed_application_ids,
)
from freedom_ls.course_applications.config import config
from freedom_ls.course_applications.forms import ApplicantDetailsForm
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.course_applications.queries import get_application_for_course
from freedom_ls.form_engine.anonymous_sittings import (
    owned_or_held_q,
    remember_anonymous_sitting,
)
from freedom_ls.form_engine.models import Form, FormProgress
from freedom_ls.form_engine.page_flow import (
    PageSubmission,
    page_context,
    render_form_page,
    resolve_page,
    submit_page,
)
from freedom_ls.form_engine.paging import (
    PageLink,
    build_page_links,
    page_link_entries,
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
            user=user,
            course=course,
            defaults={
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
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
    # A browser that still holds an unclaimed application to this course does
    # not start a second one; the claim landing attaches the held one or says
    # why it cannot.
    if unclaimed_application_for_course(request, course) is not None:
        return redirect("course_applications:claim")

    # Coming-soon courses are not enrollable — route to the detail page's
    # express-interest CTA instead of creating an application.
    if course.visibility == CourseVisibility.COMING_SOON:
        return redirect("learner_interface:course_detail", course_slug=course.slug)

    if _account_lacks_required_name(request, user):
        return _signed_in_about_you(request, user, course)
    return _apply_signed_in(request, user, course)


def _account_lacks_required_name(request: HttpRequest, user: User) -> bool:
    """Whether About you has to ask a signed-in applicant for a first name.

    Only a required field is asked for: a blank optional name never is, and
    the account always has an email.
    """
    return (
        get_effective_require_name(get_signup_policy_for_request(request))
        and not user.first_name
    )


def _apply_signed_in(request: HttpRequest, user: User, course: Course) -> HttpResponse:
    if course.application_form is not None or request.method == "POST":
        app = _start_application(user, course)
        if app.form_progress is not None:
            return redirect(_resume_url(app, app.form_progress))
        record_application_submitted(request, course)
        return redirect("course_applications:status", pk=app.pk)

    return render(
        request,
        "course_applications/apply.html",
        {"course": course},
    )


def _signed_in_about_you(
    request: HttpRequest, user: User, course: Course
) -> HttpResponse:
    """About you for a signed-in applicant, asking only for the first name the account lacks."""
    details_form = ApplicantDetailsForm(
        request.POST if request.method == "POST" else None, ask_for=("first_name",)
    )
    if request.method == "POST" and details_form.is_valid():
        user.first_name = details_form.details["first_name"]
        user.save(update_fields=["first_name"])
        return _apply_signed_in(request, user, course)
    return _render_about_you(
        request,
        course,
        details_form,
        application=None,
        form_progress=None,
        is_unclaimed=False,
    )


def _privacy_url(request: HttpRequest) -> str | None:
    site = get_cached_site(request)
    if isinstance(site, Site) and has_legal_doc(site, "privacy"):
        return reverse("accounts:legal_doc", kwargs={"doc_type": "privacy"})
    return None


def _start_cap_response(request: HttpRequest, course: Course) -> HttpResponse | None:
    """The 429 page when this address has started too many applications, else None.

    Called only where a row is about to be created, so a refused post costs
    nothing against the cap. Counted per site, as the referral hit log is: one
    address shared by a school or an office is a different crowd on each tenant.
    """
    if not is_ip_throttled(
        request,
        namespace="course_applications.anonymous_start",
        scope=str(course.site_id),
        limit=config.COURSE_APPLICATIONS_ANONYMOUS_START_LIMIT,
        window_seconds=config.COURSE_APPLICATIONS_ANONYMOUS_START_WINDOW_SECONDS,
    ):
        return None
    response = render(request, "429.html", status=429)
    response["Retry-After"] = str(
        config.COURSE_APPLICATIONS_ANONYMOUS_START_WINDOW_SECONDS
    )
    return response


def _apply_anonymous(request: HttpRequest, course: Course) -> HttpResponse:
    held = unclaimed_application_for_course(request, course)
    if held is not None:
        # An application with no sitting was sent the moment it was created,
        # so it has nowhere to resume to.
        if held.form_progress is None or held.is_submitted:
            return _redirect_to_handoff(request, held, just_sent=False)
        return redirect(_resume_url(held, held.form_progress))
    if course.visibility == CourseVisibility.COMING_SOON:
        return redirect("learner_interface:course_detail", course_slug=course.slug)
    return _apply_anonymous_about_you(request, course)


def _session_lifetime() -> timedelta | None:
    """How long a browser session, and so an unclaimed draft, lasts.

    None when the session ends with the browser, so the page can say that
    rather than name a span that does not apply.
    """
    if settings.SESSION_EXPIRE_AT_BROWSER_CLOSE:
        return None
    return timedelta(seconds=int(settings.SESSION_COOKIE_AGE))


ABOUT_YOU_TITLE = "About you"


def _about_you_url(app: CourseApplication) -> str:
    return reverse("course_applications:about_you", kwargs={"pk": app.pk})


def _with_about_you_entry(
    page_links: list[PageLink], *, url: str, is_current: bool
) -> list[PageLink]:
    """The page-jump nav of an application that starts on About you.

    The form pages keep their own URLs and numbering inside the form; only
    the displayed numbers move up by one.
    """
    about_you = PageLink(1, ABOUT_YOU_TITLE, url, is_current, True)
    return [about_you, *(replace(link, number=link.number + 1) for link in page_links)]


def _render_about_you(
    request: HttpRequest,
    course: Course,
    details_form: ApplicantDetailsForm,
    *,
    application: CourseApplication | None,
    form_progress: FormProgress | None,
    read_only: bool = False,
    return_to_check: bool = False,
    is_unclaimed: bool = True,
) -> HttpResponse:
    """Draw About you at the status its submission earned.

    With no application yet, the form pages are listed but none is reachable.
    """
    form = course.application_form
    if application is None or form_progress is None:
        entries = page_link_entries(
            list(form.pages.all()) if form is not None else [],
            0,
            0,
            lambda number: "",
        )
        about_you_url = ""
        check_answers_url = ""
    else:
        entries = build_page_links(
            form_progress.form,
            form_progress,
            0,
            lambda number: _page_url(application, number),
        )
        about_you_url = _about_you_url(application)
        check_answers_url = reverse(
            "course_applications:check_answers", kwargs={"pk": application.pk}
        )
    if return_to_check:
        submit_label = "Save and return to your answers"
    else:
        submit_label = "Next" if form is not None else "Submit application"
    refused = details_form.is_bound and not details_form.is_valid()
    submission = PageSubmission(
        required_answers_error=(
            " ".join(str(error) for error in details_form.non_field_errors())
            or "Check the details below."
        )
        if refused
        else ""
    )
    context: dict[str, object] = {
        "application": application,
        "course": course,
        "details_form": details_form,
        "page_heading": ABOUT_YOU_TITLE,
        "page_links": _with_about_you_entry(
            entries, url=about_you_url, is_current=True
        ),
        "read_only": read_only,
        "return_to_check": return_to_check,
        "check_answers_url": check_answers_url,
        "previous_page_url": None,
        # About you is always followed by a page or by check-your-answers, so
        # the read-only page never offers the last page's "Your answers" link.
        "has_next_page": True,
        "submit_label": submit_label,
        "privacy_url": _privacy_url(request),
        "is_unclaimed": is_unclaimed,
        "session_lifetime": _session_lifetime(),
        "required_answers_error": submission.required_answers_error,
        "rejected_answers_error": submission.rejected_answers_error,
    }
    return render_form_page(
        request, "course_applications/about_you.html", context, submission
    )


def _apply_anonymous_about_you(request: HttpRequest, course: Course) -> HttpResponse:
    """About you for a visitor with nothing held: no row until the details are valid."""
    form = course.application_form
    details_form = ApplicantDetailsForm(
        request.POST if request.method == "POST" else None
    )
    if request.method == "POST" and details_form.is_valid():
        capped = _start_cap_response(request, course)
        if capped is not None:
            return capped
        with transaction.atomic():
            form_progress = (
                FormProgress.objects.create(user=None, form=form)
                if form is not None
                else None
            )
            app = CourseApplication.objects.create(
                course=course, form_progress=form_progress, **details_form.details
            )
        remember_unclaimed_application(request, app)
        if form_progress is not None:
            remember_anonymous_sitting(request, form_progress)
            return redirect(_resume_url(app, form_progress))
        record_application_submitted(request, course)
        return _redirect_to_handoff(request, app, just_sent=True)
    return _render_about_you(
        request, course, details_form, application=None, form_progress=None
    )


@never_cache_same_origin
def application_about_you(request: HttpRequest, pk: UUID) -> HttpResponse:
    """The About you page of an application that already exists.

    Only an unclaimed application shows it: a claimed application's details
    are the account's, so there is nothing here for its owner to edit.
    """
    app, _form, form_progress = _application_for_request(request, pk)
    if app.is_claimed:
        return _landing_for(app)
    read_only = app.is_submitted
    if read_only and request.method == "POST":
        return _redirect_after_submission(request, app)
    # The form posts to its own URL, query string included, so the marker
    # survives a 422 re-render.
    return_to_check = request.GET.get("return") == RETURN_TO_CHECK
    details_form = ApplicantDetailsForm(
        request.POST if request.method == "POST" else None,
        initial={
            "first_name": app.first_name,
            "last_name": app.last_name,
            "email": app.email,
        },
    )
    if request.method == "POST" and details_form.is_valid():
        for name, value in details_form.details.items():
            setattr(app, name, value)
        app.save(update_fields=[*details_form.details, "updated_at"])
        if return_to_check:
            return redirect("course_applications:check_answers", pk=app.pk)
        return redirect(_resume_url(app, form_progress, page_number=1))
    return _render_about_you(
        request,
        app.course,
        details_form,
        application=app,
        form_progress=form_progress,
        read_only=read_only,
        return_to_check=return_to_check,
    )


def _redirect_to_handoff(
    request: HttpRequest, app: CourseApplication, *, just_sent: bool
) -> HttpResponse:
    """Send an anonymous applicant to create or enter the account that will own this application.

    The typed address and names prefill signup. The response is the same for a
    registered and an unregistered address: nothing here looks an account up.
    When signups are closed the visitor lands on login, so the toast only
    offers that. "Has been sent" is said once, at the submission; coming back
    to a sent application repeats the next step, not the sending.

    A signed-in visitor already has the account, so they go straight to the
    claim landing, which attaches the application or says why it cannot.
    """
    if request.user.is_authenticated:
        return redirect("course_applications:claim")
    auth_url = acquisition_auth_url(request)
    next_step = "Create an account or log in" if auth_url is not None else "Log in"
    if just_sent:
        messages.success(
            request,
            f"Your application for {app.course.title} has been sent. "
            f"{next_step} with {app.email} to see its progress.",
        )
    else:
        messages.info(
            request,
            f"{next_step} with {app.email} to see the progress of your "
            f"application for {app.course.title}.",
        )
    if auth_url is not None:
        prefill = {
            name: value
            for name, value in (
                ("email", app.email),
                ("first_name", app.first_name),
                ("last_name", app.last_name),
            )
            if value
        }
        auth_url = f"{auth_url}?{urlencode(prefill)}"
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
            {
                "application": mismatched,
                "course": mismatched.course,
                "address_unverified": has_unverified_address(
                    cast(User, request.user), mismatched.email
                ),
            },
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


def _resume_url(
    app: CourseApplication,
    form_progress: FormProgress,
    page_number: int | None = None,
) -> str:
    """Where an unfinished sitting picks back up, or `page_number` when given.

    A form with no pages has nothing to fill in, so the only place left to send
    the applicant is the page they submit from.
    """
    if not form_progress.form.pages.exists():
        return reverse("course_applications:check_answers", kwargs={"pk": app.pk})
    if page_number is None:
        page_number = resume_page_number(form_progress)
    return _page_url(app, page_number)


# Query-string marker an Edit link from the check-your-answers page carries. A
# page reached with it saves and goes straight back there instead of advancing.
RETURN_TO_CHECK = "check"


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
        "page_heading": current.page.title,
        "submit_label": (
            "Save and return to your answers" if return_to_check else "Next"
        ),
        "is_unclaimed": not app.is_claimed,
        "session_lifetime": _session_lifetime(),
    }
    if not app.is_claimed:
        context["page_links"] = _with_about_you_entry(
            cast(list[PageLink], context["page_links"]),
            url=_about_you_url(app),
            is_current=False,
        )
        if page_number == 1:
            context["previous_page_url"] = _about_you_url(app)
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
    return _redirect_to_handoff(request, app, just_sent=False)


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
    refused = False

    if request.method == "POST" and not submitted:
        unanswered = unanswered_required_in_form(form_progress)
        if unanswered:
            required_answers_error = unanswered_required_message(unanswered)
            refused = True
        else:
            form_progress.complete()
            record_application_submitted(request, app.course)
            if not app.is_claimed:
                return _redirect_to_handoff(request, app, just_sent=True)
            messages.success(
                request,
                f"Your application for {app.course.title} has been submitted "
                "and is pending review.",
            )
            return redirect("learner_interface:dashboard")
    elif request.method == "POST":
        return _redirect_after_submission(request, app)

    # Fills the answers cache once; existing_answers_dict then reads from it, so
    # the loop below makes no per-row queries.
    prefetch_related_objects(
        [form_progress], "answers__selected_options", "answers__answer_file"
    )
    sections: list[dict[str, object]] = [
        {
            "title": ABOUT_YOU_TITLE,
            "edit_url": (
                f"{_about_you_url(app)}?return={RETURN_TO_CHECK}"
                if not app.is_claimed
                else None
            ),
            "rows": [
                {"label": "Name", "text": app.full_name},
                {"label": "Email address", "text": app.email},
            ],
        }
    ]
    for number, page in enumerate(form.pages.all(), start=1):
        questions = page_questions(page)
        answers = form_progress.existing_answers_dict(questions)
        sections.append(
            {
                "title": page.title,
                "number": number,
                "edit_url": f"{_page_url(app, number)}?return={RETURN_TO_CHECK}",
                "rows": [
                    {
                        "label": question.rendered_question,
                        "question": question,
                        "answer": answers.get(question.id),
                    }
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
            "is_unclaimed": not app.is_claimed,
            "session_lifetime": _session_lifetime(),
        },
        status=422 if refused else 200,
    )
