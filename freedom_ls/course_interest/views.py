"""Views for course_interest.

HTMX partial views for expressing and removing interest in coming-soon courses.
Both views are POST-only and return the shared CTA partial. Neither carries
@login_required: that decorator sends the browser back to the current URL,
which is POST-only, so an anonymous visitor branches out to redirect_to_auth
with a next chosen for the purpose instead.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from freedom_ls.accounts.utils import redirect_to_auth
from freedom_ls.content_engine.models import Course, CourseVisibility
from freedom_ls.course_access.visibility import raise_404_if_hidden_unregistered
from freedom_ls.course_interest.models import CourseInterest

_CTA_TEMPLATE = "course_interest/partials/express_interest_cta.html"
_PENDING_INTEREST_SESSION_KEY = "course_interest_pending_slug"


@require_POST
def partial_express_interest(request: HttpRequest, course_slug: str) -> HttpResponse:
    """Express interest in a coming-soon course (HTMX, POST-only).

    An anonymous visitor is sent to sign in with next pointed at
    deferred_express_interest, the GET-safe view that records the interest
    once they return — resolved before the course lookup so an anonymous POST
    for any slug gets an identical redirect and confirms nothing about the
    course. The slug is stashed in the session so that view can tell a real
    click from a bare GET of its URL.

    Returns 404 if the course is hidden and the user is not registered (never
    confirms a hidden course exists). Returns HTTP 422 if the course is not
    COMING_SOON (validation-error path). On success, get_or_create the
    interest row (idempotent) and return the CTA partial in the interested
    state.
    """
    if not request.user.is_authenticated:
        next_url = reverse(
            "course_interest:deferred_express_interest",
            kwargs={"course_slug": course_slug},
        )
        request.session[_PENDING_INTEREST_SESSION_KEY] = course_slug
        return redirect_to_auth(request, next_url=next_url)

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


@require_POST
def partial_remove_interest(request: HttpRequest, course_slug: str) -> HttpResponse:
    """Remove interest in a coming-soon course (HTMX, POST-only).

    An anonymous visitor has no interest to remove, so there is nothing to
    defer — they are sent to sign in and return to the course detail page.

    Deletes the user's CourseInterest for this course if present; no error if
    absent. Returns the CTA partial in the not-interested state. Returns 404
    if the course is hidden and the user is not registered (matches
    express_interest — never confirms a hidden course exists).
    """
    if not request.user.is_authenticated:
        next_url = reverse(
            "learner_interface:course_detail", kwargs={"course_slug": course_slug}
        )
        return redirect_to_auth(request, next_url=next_url)

    course = get_object_or_404(Course, slug=course_slug)

    raise_404_if_hidden_unregistered(request.user, course)

    CourseInterest.objects.filter(user=request.user, course=course).delete()

    return render(
        request,
        _CTA_TEMPLATE,
        {"course": course, "is_interested": False},
    )


@login_required
def deferred_express_interest(request: HttpRequest, course_slug: str) -> HttpResponse:
    """Where an express-interest click lands once sign-in completes.

    The browser returns here with a GET, so this view cannot mirror
    partial_express_interest's POST-only contract. It records the interest
    only for the slug that view stashed in the session on the way out, so a
    forged `<img src>` or a link prefetch of this URL writes nothing.
    """
    course = get_object_or_404(Course, slug=course_slug)

    raise_404_if_hidden_unregistered(request.user, course)

    pending_slug = request.session.pop(_PENDING_INTEREST_SESSION_KEY, None)
    if (
        pending_slug == course_slug
        and course.visibility == CourseVisibility.COMING_SOON
    ):
        CourseInterest.objects.get_or_create(user=request.user, course=course)

    return redirect("learner_interface:course_detail", course_slug=course.slug)
