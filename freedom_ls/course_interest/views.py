"""Views for course_interest.

HTMX partial views for expressing and removing interest in coming-soon courses.
Both views are POST-only, require login, and return the shared CTA partial.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from freedom_ls.content_engine.models import Course, CourseVisibility
from freedom_ls.course_access.visibility import raise_404_if_hidden_unregistered
from freedom_ls.course_interest.models import CourseInterest

_CTA_TEMPLATE = "course_interest/partials/express_interest_cta.html"


@login_required
@require_POST
def partial_express_interest(request: HttpRequest, course_slug: str) -> HttpResponse:
    """Express interest in a coming-soon course (HTMX, POST-only).

    Returns 404 if the course is hidden and the user is not registered (matches
    course_detail / spec §13 — never confirms a hidden course exists). Returns
    HTTP 422 if the course is not COMING_SOON (validation-error path). On success,
    get_or_create the interest row (idempotent) and return the CTA partial in the
    interested state.
    """
    course = get_object_or_404(Course, slug=course_slug)

    raise_404_if_hidden_unregistered(request.user, course)
    if course.visibility != CourseVisibility.COMING_SOON:
        return HttpResponse(status=422)

    CourseInterest.objects.get_or_create(user=request.user, course=course)

    return render(
        request,
        _CTA_TEMPLATE,
        {"course": course, "is_interested": True},
    )


@login_required
@require_POST
def partial_remove_interest(request: HttpRequest, course_slug: str) -> HttpResponse:
    """Remove interest in a coming-soon course (HTMX, POST-only).

    Deletes the user's CourseInterest for this course if present; no error if absent.
    Returns the CTA partial in the not-interested state. Returns 404 if the course
    is hidden and the user is not registered (matches express_interest — never
    confirms a hidden course exists).
    """
    course = get_object_or_404(Course, slug=course_slug)

    raise_404_if_hidden_unregistered(request.user, course)

    CourseInterest.objects.filter(user=request.user, course=course).delete()

    return render(
        request,
        _CTA_TEMPLATE,
        {"course": course, "is_interested": False},
    )
