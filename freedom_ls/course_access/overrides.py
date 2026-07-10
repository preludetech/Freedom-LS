from __future__ import annotations

from typing import TYPE_CHECKING

from freedom_ls.course_access.config import config

if TYPE_CHECKING:
    from freedom_ls.content_engine.models import Course


def override_visibility_to_visible() -> bool:
    """True when every course should be treated as visible (dev/staging preview)."""
    return bool(config.OVERRIDE_COURSE_VISIBILITY_TO_VISIBLE)


def override_access_to_free() -> bool:
    """True when every course should be treated as freely accessible (dev/staging preview)."""
    return bool(config.OVERRIDE_COURSE_ACCESS_TO_FREE)


def is_coming_soon_for_display(course: Course) -> bool:
    """Whether a course should present as coming-soon, honouring the visibility override."""
    from freedom_ls.content_engine.models import CourseVisibility

    return (
        course.visibility == CourseVisibility.COMING_SOON
        and not override_visibility_to_visible()
    )
