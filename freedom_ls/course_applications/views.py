"""Views for course_applications."""

from __future__ import annotations

from typing import cast
from urllib.parse import urlencode
from uuid import UUID

from allauth.account.adapter import get_adapter
from allauth.core import ratelimit

from django.contrib import messages
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.db import transaction
from django.db.models import QuerySet, prefetch_related_objects
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.crypto import salted_hmac

from freedom_ls.accounts.models import User
from freedom_ls.accounts.utils import (
    get_client_ip,
    redirect_to_acquisition_auth,
    redirect_to_auth,
)
from freedom_ls.content_engine.models import Course
from freedom_ls.course_access import get_course_access_backend
from freedom_ls.course_access.analytics_events import record_application_submitted
from freedom_ls.course_access.overrides import is_coming_soon_for_display
from freedom_ls.course_access.visibility import raise_404_if_hidden_unregistered
from freedom_ls.course_applications.anonymous_session import (
    anonymous_applicant_for_course,
    application_of,
    forget_anonymous_applicant,
    owned_applications,
    remember_anonymous_applicant,
)
from freedom_ls.course_applications.applicant_email import (
    email_rate_limit_key,
    normalise_email,
)
from freedom_ls.course_applications.backends import APPLICATION_GATED
from freedom_ls.course_applications.claims import (
    ClaimOwner,
    attach_claimed_application,
    claim_sets_a_password,
    read_claim_token,
    resolve_claim_owner,
    update_applicant_email,
)
from freedom_ls.course_applications.emails import send_application_claim_email
from freedom_ls.course_applications.forms import ApplicantDetailsForm
from freedom_ls.course_applications.models import AnonymousApplicant, CourseApplication
from freedom_ls.course_applications.queries import get_application_for_course
from freedom_ls.form_engine.models import Form, FormProgress
from freedom_ls.form_engine.page_flow import (
    PageSubmission,
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
from freedom_ls.form_engine.session_access import allow_anonymous_form_progress
from freedom_ls.site_aware_models.models import get_cached_site


def _start_application(
    course: Course,
    *,
    user: User | None = None,
    anonymous_applicant: AnonymousApplicant | None = None,
) -> CourseApplication:
    """The applicant's application to this course, created if they have none.

    The applicant is a signed-in user or an anonymous applicant, never both.

    A course that names an application form gets a sitting of that form created
    alongside the application; the sitting is a draft, not a submission.
    """
    with transaction.atomic():
        # get_or_create is race-safe (savepoint + IntegrityError catch +
        # re-get), so concurrent requests that both pass the existing-application
        # check still converge on one row. An account holds one application
        # per course however it began, so a user's lookup is by course alone.
        app: CourseApplication
        app, _ = CourseApplication.objects.get_or_create(
            course=course,
            **(
                {"user": user}
                if user is not None
                else {"anonymous_applicant": anonymous_applicant}
            ),
        )
        # Locked before the sitting check: without it two overlapping calls
        # both see no sitting, each creates one, and the loser's sitting is
        # left with no user and no application to reach it by.
        app = CourseApplication.objects.select_for_update().get(pk=app.pk)
        if course.application_form is not None and app.form_progress is None:
            app.form_progress = FormProgress.objects.create(
                user=user, form=course.application_form
            )
            app.save(update_fields=["form_progress"])
    return app


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

    An anonymous visitor is sent through the applicant details step first (see
    `applicant_details`); no account exists for them until they follow the
    claim link in the confirmation email.

    NOTE: when application review lands, the POST body will wrap get_or_create in
      an atomic block and call app.submit() (the FSM transition) + create an
      ApplicationStateTransition audit row.
    """
    course = get_object_or_404(Course, slug=course_slug)

    # Enforce course visibility: hidden courses 404 for unregistered users.
    raise_404_if_hidden_unregistered(request.user, course)

    if not request.user.is_authenticated:
        return _anonymous_apply(request, course)
    user = cast(User, request.user)

    # An existing applicant always reaches their application record, even if the
    # course was later flipped to coming-soon — so this short-circuit precedes the
    # coming-soon redirect below.
    existing_app = get_application_for_course(user=user, course=course)
    if existing_app is not None:
        return redirect("course_applications:status", pk=existing_app.pk)

    coming_soon = _coming_soon_redirect(course)
    if coming_soon is not None:
        return coming_soon

    if course.application_form is not None or request.method == "POST":
        app = _start_application(course, user=user)
        if app.form_progress is not None:
            return redirect(_resume_url(app, app.form_progress))
        record_application_submitted(request, course)
        return redirect("course_applications:status", pk=app.pk)

    return render(
        request,
        "course_applications/apply.html",
        {"course": course},
    )


def application_status(request: HttpRequest, pk: UUID) -> HttpResponse:
    """Applicant status page.

    Shows a static plain-language "received and pending review" confirmation.
    Only the application owner may view this page: another user gets 404 and a
    visitor is sent to log in. Ownership covers an anonymous session's own
    unverified application.

    An application whose form is still unfinished is sent back to it: there is
    nothing to say about a request that has not been made yet.

    POST, for an unverified application, sends the claim email again. The
    page says whether an email has gone out at all, so an applicant whose
    first one was skipped or lost is never left waiting for it.

    NOTE: when application review lands, dynamic state rendering (state badge,
      reviewer message, withdraw action via get_available_user_state_transitions)
      goes here.
    """
    found = _owned_application(
        request,
        owned_applications(request).select_related(
            "course", "form_progress", "anonymous_applicant"
        ),
        pk,
    )
    if isinstance(found, HttpResponse):
        return found
    app = found
    if app.form_progress is not None and app.form_progress.completed_time is None:
        return redirect(_resume_url(app, app.form_progress))
    if request.method == "POST":
        if app.anonymous_applicant is None or app.is_email_verified:
            raise Http404
        applicant = app.anonymous_applicant
        if send_application_claim_email(request, applicant):
            messages.success(request, f"We've emailed a link to {applicant.email}.")
        else:
            messages.error(
                request,
                f"We couldn't email {applicant.email} just now. "
                "Try again in a little while.",
            )
        return redirect("course_applications:status", pk=app.pk)
    return render(
        request,
        "course_applications/application_status.html",
        {"application": app},
    )


def _anonymous_applications_allowed(course: Course) -> bool:
    """Only an application-gated course takes applications from a visitor.

    Any other course is entered by signing up, so a visitor applying to one
    is sent to the auth page the way every acquisition call to action does.
    """
    backend = get_course_access_backend()
    return backend.get_access_type(course=course) == APPLICATION_GATED


def _coming_soon_redirect(course: Course) -> HttpResponse | None:
    """Coming-soon courses are not enrollable: the detail page's express-interest
    call to action is the only thing on offer. Honours the dev/staging override
    that previews such a course as visible."""
    if not is_coming_soon_for_display(course):
        return None
    return redirect("learner_interface:course_detail", course_slug=course.slug)


def _anonymous_apply(request: HttpRequest, course: Course) -> HttpResponse:
    if not _anonymous_applications_allowed(course):
        return redirect_to_acquisition_auth(request)
    applicant = anonymous_applicant_for_course(request, course)
    app = application_of(applicant) if applicant is not None else None
    # An existing application is always reachable, so this precedes the
    # coming-soon redirect just as it does for a signed-in applicant.
    if app is not None:
        if not app.is_submitted and app.form_progress is not None:
            return redirect(_resume_url(app, app.form_progress))
        return redirect("course_applications:status", pk=app.pk)
    coming_soon = _coming_soon_redirect(course)
    if coming_soon is not None:
        return coming_soon
    if applicant is None:
        return redirect(
            "course_applications:applicant_details", course_slug=course.slug
        )
    if course.application_form is not None or request.method == "POST":
        app = _start_application(course, anonymous_applicant=applicant)
        if app.form_progress is not None:
            # The course gained a form after the details step, so there is a
            # sitting to fill in before anything is submitted.
            allow_anonymous_form_progress(request, app.form_progress)
            return redirect(_resume_url(app, app.form_progress))
        record_application_submitted(request, course)
        send_application_claim_email(request, applicant)
        return redirect("course_applications:status", pk=app.pk)
    return render(
        request,
        "course_applications/apply.html",
        {
            "course": course,
            "previous_page_url": reverse(
                "course_applications:applicant_details",
                kwargs={"course_slug": course.slug},
            ),
        },
    )


DETAILS_RATE_LIMIT_ACTION = "application_details"
# How long two overlapping first POSTs from one visitor count as one.
DETAILS_IN_FLIGHT_SECONDS = 10


def _details_in_flight_key(request: HttpRequest, course: Course, email: str) -> str:
    """One cache key per visitor-and-address pair, with nothing readable in it.

    The address, the IP and the session together: a double click comes from
    one browser, and two people sharing an address on different networks are
    not one. Hashed because the production cache is a database table whose
    rows outlive their expiry, so the plain pair would sit there in clear
    text, and because a long address would push the key past the column.
    """
    fingerprint = ":".join(
        (
            str(course.pk),
            email,
            get_client_ip(request),
            request.session.session_key or "",
        )
    )
    digest = salted_hmac(
        "course_applications.details_in_flight", fingerprint
    ).hexdigest()
    return f"course_applications:details:{digest[:32]}"


def applicant_details(request: HttpRequest, course_slug: str) -> HttpResponse:
    """The step before the form that asks an anonymous visitor who they are.

    The rate limit guards the address that will receive a claim email, so it
    is spent when an applicant is created or re-addressed, and on a honeypot
    trip, never on a typo or a name change. A POST that would spend an
    exhausted bucket is refused before validation, so nothing is written for
    a limited address. A POST that would not spend it is never refused: the
    bucket is shared by everyone who posts that address, and the applicant
    who already holds it must still be able to correct their name.
    """
    if request.user.is_authenticated:
        return redirect("course_applications:apply", course_slug=course_slug)
    course = get_object_or_404(Course, slug=course_slug)
    raise_404_if_hidden_unregistered(request.user, course)
    if not _anonymous_applications_allowed(course):
        return redirect_to_acquisition_auth(request)
    applicant = anonymous_applicant_for_course(request, course)
    app = application_of(applicant) if applicant is not None else None
    if app is not None and app.is_submitted:
        return redirect("course_applications:status", pk=app.pk)
    if app is None:
        coming_soon = _coming_soon_redirect(course)
        if coming_soon is not None:
            return coming_soon
    instance = applicant if applicant is not None else AnonymousApplicant(course=course)
    status = 200
    if request.method == "POST":
        site = get_cached_site(request)
        if not isinstance(site, Site):
            # A host that resolves no Site could not save the applicant either.
            raise Http404
        posted_email = request.POST.get("email", "")
        key = email_rate_limit_key(site, posted_email)
        # Read before validation: a ModelForm writes its cleaned data onto the
        # instance while validating, so afterwards the two always agree.
        previous_email = applicant.email if applicant is not None else None
        would_spend = normalise_email(posted_email) != previous_email
        if would_spend and not ratelimit.consume(
            request, action=DETAILS_RATE_LIMIT_ACTION, key=key, dry_run=True
        ):
            refused: HttpResponse = ratelimit.respond_429(request)
            return refused
        form = ApplicantDetailsForm(request.POST, request=request, instance=instance)
        if form.is_valid():
            email: str = form.cleaned_data["email"]
            address_changed = email != previous_email
            if address_changed:
                limited: HttpResponse | None = ratelimit.consume_or_429(
                    request, action=DETAILS_RATE_LIMIT_ACTION, key=key
                )
                if limited is not None:
                    return limited
            if applicant is None and not cache.add(
                _details_in_flight_key(request, course, email),
                1,
                DETAILS_IN_FLIGHT_SECONDS,
            ):
                # A double-clicked Next: the first POST is making the applicant,
                # and the GET this sends will pick that one up from the session.
                return redirect(
                    "course_applications:applicant_details", course_slug=course.slug
                )
            if applicant is not None and previous_email is not None and address_changed:
                # Validation already wrote the posted address onto the instance.
                # The stored one goes back first, so the change runs through the
                # one helper that invalidates the links sent to it.
                applicant.email = previous_email
                update_applicant_email(applicant, email)
            applicant = form.save()
            remember_anonymous_applicant(request, applicant)
            if course.application_form is None:
                return redirect("course_applications:apply", course_slug=course.slug)
            app = _start_application(course, anonymous_applicant=applicant)
            if app.form_progress is not None:
                allow_anonymous_form_progress(request, app.form_progress)
                if address_changed:
                    # The result is reported by the notice on the next page, not
                    # here: the applicant carries on into the form whether or not
                    # the email went out.
                    send_application_claim_email(request, applicant)
                return redirect(_resume_url(app, app.form_progress))
            return redirect("course_applications:status", pk=app.pk)
        if form.tripped_honeypot:
            ratelimit.consume(request, action=DETAILS_RATE_LIMIT_ACTION, key=key)
        status = 422
    else:
        form = ApplicantDetailsForm(request=request, instance=instance)
    return render(
        request,
        "course_applications/applicant_details.html",
        {"course": course, "form": form},
        status=status,
    )


def _owned_application(
    request: HttpRequest, queryset: QuerySet[CourseApplication], pk: UUID
) -> CourseApplication | HttpResponse:
    """The applicant's own application, or the response that stands in for it.

    A signed-in user who owns no such application gets 404. A visitor is sent
    to log in instead, whether or not the application exists: an owner whose
    session has ended is the usual case, and the login page returns them here.
    """
    app = queryset.filter(pk=pk).first()
    if app is not None:
        return app
    if request.user.is_authenticated:
        raise Http404
    return redirect_to_auth(request, next_url=request.get_full_path())


def _owned_application_with_form(
    request: HttpRequest, pk: UUID
) -> tuple[CourseApplication, Form, FormProgress] | HttpResponse:
    """The applicant's own application, and the form sitting it actually has.

    Returns all three because an application with no sitting has no form pages
    to show, and 404 is the honest answer for a URL that names one.

    A visitor's session reaches the sitting only while it is a draft. Once
    submitted, the answers and files wait for whoever follows the claim link,
    not for the next person at the same computer.
    """
    found = _owned_application(
        request,
        owned_applications(request).select_related(
            "course", "form_progress__form", "anonymous_applicant"
        ),
        pk,
    )
    if isinstance(found, HttpResponse):
        return found
    app = found
    if app.form_progress is None or (app.user_id is None and app.is_submitted):
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


def application_form_page(
    request: HttpRequest, pk: UUID, page_number: int
) -> HttpResponse:
    """One page of the application form.

    A submitted application is read-only for its signed-in owner: its pages
    still render, so they can re-read what they said, but nothing more is
    written to it. A visitor's session reaches only a draft (see
    `_owned_application_with_form`).
    """
    owned = _owned_application_with_form(request, pk)
    if isinstance(owned, HttpResponse):
        return owned
    app, form, form_progress = owned
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
            return redirect("course_applications:status", pk=app.pk)
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
    }
    if app.user_id is None and page_number == 1:
        context["previous_page_url"] = reverse(
            "course_applications:applicant_details",
            kwargs={"course_slug": app.course.slug},
        )
    return render_form_page(
        request, "course_applications/form_page.html", context, submission
    )


def application_check_answers(request: HttpRequest, pk: UUID) -> HttpResponse:
    """Everything the applicant has said, one card per page, and the one place
    they submit from.

    The whole-form check is what catches a required question on a page they
    never visited -- the per-page check cannot see those.
    """
    owned = _owned_application_with_form(request, pk)
    if isinstance(owned, HttpResponse):
        return owned
    app, form, form_progress = owned
    submitted = form_progress.completed_time is not None
    required_answers_error = ""

    if request.method == "POST" and not submitted:
        unanswered = unanswered_required_in_form(form_progress)
        if not unanswered:
            form_progress.complete()
            record_application_submitted(request, app.course)
            if not app.is_email_verified:
                return redirect("course_applications:status", pk=app.pk)
            messages.success(
                request,
                f"Your application for {app.course.title} has been submitted "
                "and is pending review.",
            )
            return redirect("learner_interface:dashboard")
        required_answers_error = unanswered_required_message(unanswered)
    elif request.method == "POST":
        return redirect("course_applications:status", pk=app.pk)

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

    response = render(
        request,
        "course_applications/check_your_answers.html",
        {
            "application": app,
            "course": app.course,
            "sections": sections,
            "submitted": submitted,
            "required_answers_error": required_answers_error,
        },
        status=422 if required_answers_error else 200,
    )
    response["Cache-Control"] = "no-store"
    return response


def _render_claim(
    request: HttpRequest,
    claim_state: str,
    applicant: AnonymousApplicant | None = None,
    **extra: object,
) -> HttpResponse:
    response = render(
        request,
        "course_applications/claim.html",
        {
            "claim_state": claim_state,
            "course": applicant.course if applicant is not None else None,
            **extra,
        },
    )
    # The URL is a login token; nothing on this page may be cached against it.
    response["Cache-Control"] = "no-store"
    return response


def _signed_in_as_somebody_else(request: HttpRequest, owner: ClaimOwner | None) -> bool:
    if not request.user.is_authenticated:
        return False
    return owner is None or owner.user.pk != request.user.pk


def claim_application(request: HttpRequest, token: str) -> HttpResponse:
    """Follow the emailed link: confirm on GET, claim on POST.

    GET changes nothing because mail scanners fetch links. Every way the link
    can be unusable renders the same page, so a guessed or reused token learns
    nothing about who applied. The confirm page names the address and what
    confirming does to it, because the holder of the link already has the
    email it arrived in.
    """
    link = read_claim_token(token)
    application = application_of(link.applicant) if link is not None else None
    if link is None or link.applicant.claimed_at is not None or application is None:
        return _render_claim(request, "invalid")
    is_submitted = application.is_submitted
    if link.expired:
        if request.method == "POST":
            if send_application_claim_email(request, link.applicant):
                return _render_claim(
                    request, "resent", link.applicant, is_submitted=is_submitted
                )
            return _render_claim(
                request,
                "expired",
                link.applicant,
                is_submitted=is_submitted,
                resend_failed=True,
            )
        return _render_claim(
            request, "expired", link.applicant, is_submitted=is_submitted
        )
    owner = resolve_claim_owner(link.applicant)
    if owner is not None and owner.user.site_id != link.applicant.site_id:
        return _render_claim(request, "invalid")
    if request.method != "POST":
        held = (
            CourseApplication.objects.filter(
                user=owner.user, course=link.applicant.course
            )
            .select_related("form_progress")
            .first()
            if owner is not None
            else None
        )
        held_application = (
            "" if held is None else ("submitted" if held.is_submitted else "draft")
        )
        return _render_claim(
            request,
            "confirm",
            link.applicant,
            applicant_email=link.applicant.email,
            is_submitted=is_submitted,
            held_application=held_application,
            sets_password=claim_sets_a_password(owner),
            signed_in_as=(
                cast(User, request.user).email
                if _signed_in_as_somebody_else(request, owner)
                else ""
            ),
        )
    adapter = get_adapter(request)
    if _signed_in_as_somebody_else(request, owner):
        # The confirm page said this would happen. Before the claim, because
        # signing out empties the session, and the sign-up analytics event a
        # new account records has to land in the session the claimant keeps.
        adapter.logout(request)
    outcome = attach_claimed_application(request, application)
    if outcome is None:
        return _render_claim(request, "invalid")
    forget_anonymous_applicant(request, link.applicant)
    if not outcome.user.is_active:
        return redirect("account_login")
    if request.user.is_authenticated and request.user.pk != outcome.user.pk:
        # Only reachable if the owner changed between the two lookups; the
        # hand-over must not rest on login() noticing the other account.
        adapter.logout(request)
    # Logging in cycles the session key, so the anonymous session's identifier
    # never carries over into the signed-in one.
    adapter.login(request, outcome.user)
    status_url = reverse(
        "course_applications:status", kwargs={"pk": outcome.application.pk}
    )
    if outcome.must_set_password:
        return redirect(
            f"{reverse('account_set_password')}?{urlencode({'next': status_url})}"
        )
    return redirect(status_url)
