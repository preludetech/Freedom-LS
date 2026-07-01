"""Views for course_applications."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course, CourseVisibility
from freedom_ls.course_access.visibility import raise_404_if_hidden_unregistered
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.course_applications.queries import get_application_for_course


@login_required
def apply(request: HttpRequest, course_slug: str) -> HttpResponse:
    """Apply entry view.

    GET: show confirmation page ("Apply to <course>?").
         If the learner already has an application, redirect to its status page.
    POST: get_or_create the application, then redirect to status page.

    NOTE: when application review lands, the POST body will wrap get_or_create in
      an atomic block and call app.submit() (the FSM transition) + create an
      ApplicationStateTransition audit row.
    NOTE: when application forms land, the POST body will resolve the
      ApplicationConfig, create a draft application, and redirect to the
      multi-step form flow instead.
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
        return redirect("student_interface:course_detail", course_slug=course.slug)

    if request.method == "POST":
        # get_or_create is race-safe (savepoint + IntegrityError catch + re-get), so
        # concurrent POSTs that both pass the pre-check above still converge on one row.
        app, _ = CourseApplication.objects.get_or_create(user=user, course=course)
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

    NOTE: when application review lands, dynamic state rendering (state badge,
      reviewer message, withdraw action via get_available_user_state_transitions)
      goes here.
    """
    app = get_object_or_404(CourseApplication, pk=pk, user=request.user)
    return render(
        request,
        "course_applications/application_status.html",
        {"application": app},
    )
