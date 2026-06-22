"""Views for course_applications (Tasks B.4, B.5)."""

from __future__ import annotations

from uuid import UUID

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from freedom_ls.content_engine.models import Course
from freedom_ls.course_applications.models import CourseApplication


@login_required
def apply(request: HttpRequest, course_slug: str) -> HttpResponse:
    """Apply entry view (Task B.4).

    GET: show confirmation page ("Apply to <course>?").
         If the learner already has an application, redirect to its status page.
    POST: get_or_create the application, then redirect to status page.

    NOTE (review spec): the POST body will wrap get_or_create in an atomic block
      and call app.submit() (the FSM transition) + create an ApplicationStateTransition
      audit row when the review spec is implemented.
    NOTE (forms spec): the POST body will resolve the ApplicationConfig, create a
      draft application, and redirect to the multi-step form flow instead.
    """
    course = get_object_or_404(Course, slug=course_slug)

    existing_app = CourseApplication.objects.filter(
        user=request.user, course=course
    ).first()
    if existing_app is not None:
        return redirect("course_applications:status", pk=existing_app.pk)

    if request.method == "POST":
        # get_or_create is race-safe (savepoint + IntegrityError catch + re-get), so
        # concurrent POSTs that both pass the pre-check above still converge on one row.
        app, _ = CourseApplication.objects.get_or_create(
            user=request.user, course=course
        )
        return redirect("course_applications:status", pk=app.pk)

    return render(
        request,
        "course_applications/apply.html",
        {"course": course},
    )


@login_required
def application_status(request: HttpRequest, pk: UUID) -> HttpResponse:
    """Applicant status page (Task B.5).

    Shows a static plain-language "received and pending review" confirmation.
    Only the application owner may view this page — non-owners get 404.

    NOTE (review spec): dynamic state rendering (state badge, reviewer message,
      withdraw action via get_available_user_state_transitions) goes here.
    """
    app = get_object_or_404(CourseApplication, pk=pk, user=request.user)
    return render(
        request,
        "course_applications/application_status.html",
        {"application": app},
    )
