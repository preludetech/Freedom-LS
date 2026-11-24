"""Shared availability gate for view chokepoints.

Centralises the rules that make a course a 404 for a user: a retired course, a hidden course
the user is not registered for, and a course the user is not in the audience
of. Every view surface (course detail, apply, express-interest) enforces them
identically and cannot drift from the VisibilityEnforcingBackend's
filter_visible rule.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.http import Http404

if TYPE_CHECKING:
    from freedom_ls.content_engine.models import Course
    from freedom_ls.learner_management.utils import RequestUser


def raise_404_if_unavailable(user: RequestUser, course: Course) -> None:
    """404 for a retired course, for a hidden course the user is not registered
    for, and for a course the user is not in the audience of. A registered
    learner keeps the last two, mirroring filter_visible and get_access; a
    retired course is closed to them and to the visibility override too."""
    # Lazy imports mirror backends.py: avoid a module-load import cycle.
    from freedom_ls.content_engine.models import CourseVisibility
    from freedom_ls.course_access.overrides import override_visibility_to_visible
    from freedom_ls.learner_management.queries import is_in_audience
    from freedom_ls.learner_management.utils import is_registered_for_course

    if course.is_retired:
        raise Http404

    if override_visibility_to_visible():
        return

    if course.visibility == CourseVisibility.HIDDEN and not is_registered_for_course(
        user, course
    ):
        raise Http404

    if not is_in_audience(user, course):
        raise Http404
