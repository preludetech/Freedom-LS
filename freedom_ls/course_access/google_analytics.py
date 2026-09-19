"""The GA4 parameters every course event carries."""

from __future__ import annotations

from typing import TYPE_CHECKING

from freedom_ls.course_access import get_course_access_backend

if TYPE_CHECKING:
    from freedom_ls.content_engine.models import Course


def course_event_params(course: Course) -> dict[str, str]:
    """Which course a GA4 event was about, and how that course is entered.

    `course_id` is the UUID the course webhooks carry, so GA4 data joins to
    webhook data and survives a slug rename. `course_slug` is the readable one
    and matches the page URLs GA4 already records.
    """
    return {
        "course_slug": course.slug,
        "course_id": str(course.id),
        "access_type": get_course_access_backend().get_access_type(course=course),
    }
