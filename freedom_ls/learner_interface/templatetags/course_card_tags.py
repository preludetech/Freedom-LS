"""Template filters for the ``c-course-card`` markdown widget."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django import template

from freedom_ls.content_engine.models import Course, CourseVisibility
from freedom_ls.course_access import get_course_access_backend

if TYPE_CHECKING:
    from freedom_ls.content_base.models import BaseContent
    from freedom_ls.course_access.backends import AccessBadge

register = template.Library()


@register.filter
def get_course_by_path(
    file_path: str | None, content_instance: BaseContent
) -> Course | None:
    """Look up a visible Course by its file_path, relative to *content_instance*.

    Usage: ``{{ "../course/course.md"|get_course_by_path:content_instance }}``
    """
    file_path = (file_path or "").strip()
    if not file_path:
        return None

    final_path = content_instance.calculate_path_from_root(file_path)

    # Filter on the content's own site, not the thread-local one: body markdown
    # is also rendered where no request has pinned a site.
    return (
        Course._base_manager.filter(
            site_id=content_instance.site_id, file_path=final_path
        )
        .exclude(visibility=CourseVisibility.HIDDEN)
        .first()
    )


@register.filter
def course_access_badge(course: Course) -> AccessBadge | None:
    """The active access backend's at-a-glance badge for *course*."""
    return get_course_access_backend().get_access_badge(course=course)
