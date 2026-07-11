"""Shared visibility gate for view chokepoints.

Centralises the "hidden courses 404 for anyone not registered" rule so that
every view surface (course detail, apply, express-interest) enforces it
identically and cannot drift from the VisibilityEnforcingBackend's filter_visible
rule (spec §13: hidden means hidden).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.http import Http404

if TYPE_CHECKING:
    from freedom_ls.content_engine.models import Course
    from freedom_ls.student_management.utils import RequestUser


def raise_404_if_hidden_unregistered(user: RequestUser, course: Course) -> None:
    """Raise Http404 if the course is hidden and the user is not registered for it.

    A registered learner keeps access to a hidden course (mirrors filter_visible
    and get_access), so only unregistered users get the 404.
    """
    # Lazy imports mirror backends.py — avoid a module-load import cycle.
    from freedom_ls.content_engine.models import CourseVisibility
    from freedom_ls.course_access.overrides import override_visibility_to_visible
    from freedom_ls.student_management.utils import is_registered_for_course

    if override_visibility_to_visible():
        return

    if course.visibility == CourseVisibility.HIDDEN and not is_registered_for_course(
        user, course
    ):
        raise Http404
