"""Views for course_applications."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import prefetch_related_objects
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course, CourseVisibility
from freedom_ls.course_access.visibility import raise_404_if_hidden_unregistered
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.course_applications.queries import get_application_for_course
from freedom_ls.form_engine.models import Form, FormProgress
from freedom_ls.form_engine.paging import (
    build_page_links,
    resume_page_number,
    unanswered_required_in_form,
    unanswered_required_message,
    unanswered_required_on_page,
)
from freedom_ls.form_engine.queries import page_questions


@login_required
def apply(request: HttpRequest, course_slug: str) -> HttpResponse:
    """Apply entry view.

    GET: show confirmation page ("Apply to <course>?").
         If the learner already has an application, redirect to its status page.
    POST: get_or_create the application, then redirect to status page.

    NOTE: when application review lands, the POST body will wrap get_or_create in
      an atomic block and call app.submit() (the FSM transition) + create an
      ApplicationStateTransition audit row.
    A course that names an application form gets a sitting of that form created
    alongside the application, and the applicant is sent to its first page. A
    course that names none goes straight to the status page as before.
    """
    course = get_object_or_404(Course, slug=course_slug)
    user = cast(User, request.user)  # login_required guarantees an authenticated User

    # Enforce course visibility: hidden courses 404 for unregistered users.
    raise_404_if_hidden_unregistered(user, course)

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

    if request.method == "POST":
        with transaction.atomic():
            # get_or_create is race-safe (savepoint + IntegrityError catch +
            # re-get), so concurrent POSTs that both pass the pre-check above
            # still converge on one row.
            app, _ = CourseApplication.objects.get_or_create(user=user, course=course)
            if course.application_form is not None and app.form_progress is None:
                app.form = course.application_form
                app.form_progress = FormProgress.objects.create(
                    user=user, form=app.form
                )
                app.save(update_fields=["form", "form_progress"])
        if app.form_progress is not None:
            return redirect("course_applications:form_page", pk=app.pk, page_number=1)
        return redirect("course_applications:status", pk=app.pk)

    return render(
        request,
        "course_applications/apply.html",
        {"course": course},
    )


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
        return redirect(
            "course_applications:form_page",
            pk=app.pk,
            page_number=resume_page_number(app.form_progress),
        )
    return render(
        request,
        "course_applications/application_status.html",
        {"application": app},
    )


def _owned_application_with_form(
    request: HttpRequest, pk: UUID
) -> tuple[CourseApplication, Form, FormProgress]:
    """The applicant's own application, and the form sitting it actually has.

    Returns all three because an application with no sitting has no form pages
    to show, and 404 is the honest answer for a URL that names one.
    """
    app: CourseApplication = get_object_or_404(
        CourseApplication.objects.select_related("course", "form", "form_progress"),
        pk=pk,
        user=request.user,
    )
    if app.form is None or app.form_progress is None:
        raise Http404
    return app, app.form, app.form_progress


def _page_url(app: CourseApplication, page_number: int) -> str:
    return reverse(
        "course_applications:form_page",
        kwargs={"pk": app.pk, "page_number": page_number},
    )


# Query-string marker an Edit link from the check-your-answers page carries. A
# page reached with it saves and goes straight back there instead of advancing.
RETURN_TO_CHECK = "check"


@login_required
def application_form_page(
    request: HttpRequest, pk: UUID, page_number: int
) -> HttpResponse:
    """One page of the application form.

    A submission that misses a required question is refused, but the answers it
    did carry are saved first: throwing away the work someone did do, because of
    the one field they missed, is the cruellest thing a form can do.
    """
    app, form, form_progress = _owned_application_with_form(request, pk)
    all_pages = list(form.pages.all())
    if not 1 <= page_number <= len(all_pages):
        raise Http404
    form_page = all_pages[page_number - 1]
    questions = page_questions(form_page)
    read_only = form_progress.completed_time is not None
    # The page form posts to its own URL, query string included, so the marker
    # survives both the save and a 422 re-render.
    return_to_check = request.GET.get("return") == RETURN_TO_CHECK

    def url_for_page(number: int) -> str:
        return _page_url(app, number)

    required_answers_error = ""
    if request.method == "POST":
        if read_only:
            return redirect("course_applications:status", pk=app.pk)
        unanswered = unanswered_required_on_page(questions, request.POST, form_progress)
        form_progress.save_answers(questions, request.POST)
        if not unanswered:
            if page_number < len(all_pages) and not return_to_check:
                return redirect(url_for_page(page_number + 1))
            return redirect("course_applications:check_answers", pk=app.pk)
        required_answers_error = unanswered_required_message(unanswered)

    context = {
        "application": app,
        "course": app.course,
        "form": form,
        "form_page": form_page,
        "form_progress": form_progress,
        "current_page_num": page_number,
        "total_pages": len(all_pages),
        "previous_page_url": url_for_page(page_number - 1) if page_number > 1 else None,
        "has_next_page": page_number < len(all_pages),
        "existing_answers": form_progress.existing_answers_dict(questions),
        "page_links": build_page_links(form, form_progress, page_number, url_for_page),
        "read_only": read_only,
        "required_answers_error": required_answers_error,
        "return_to_check": return_to_check,
        "check_answers_url": reverse(
            "course_applications:check_answers", kwargs={"pk": app.pk}
        ),
    }
    response = render(
        request,
        "course_applications/form_page.html",
        context,
        status=422 if required_answers_error else 200,
    )
    # Re-fetch on back-nav, so a page never shows answers that have since changed.
    response["Cache-Control"] = "no-store"
    return response


@login_required
def application_check_answers(request: HttpRequest, pk: UUID) -> HttpResponse:
    """Everything the applicant has said, one card per page, and the one place
    they submit from.

    The whole-form check is what catches a required question on a page they
    never visited -- the per-page check cannot see those.
    """
    app, form, form_progress = _owned_application_with_form(request, pk)
    submitted = form_progress.completed_time is not None
    required_answers_error = ""

    if request.method == "POST" and not submitted:
        unanswered = unanswered_required_in_form(form_progress)
        if not unanswered:
            form_progress.complete()
            return redirect("course_applications:status", pk=app.pk)
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
