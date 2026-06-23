"""Query helpers for course_applications.

These helpers are consumed by the ApplicationCourseAccessBackend and this app's own
views. student_interface must NOT import from here — it reaches the applications
panel only through backend.get_dashboard_contributions().
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from freedom_ls.accounts.models import User
    from freedom_ls.content_engine.models import Course
    from freedom_ls.course_applications.models import CourseApplication


def get_application_for_course(
    *, user: User, course: Course
) -> CourseApplication | None:
    """Return this user's application to the given course, or None.

    Site isolation is automatic via SiteAwareManager.
    """
    from freedom_ls.course_applications.models import CourseApplication

    return CourseApplication.objects.filter(user=user, course=course).first()


def get_active_applications(user: User) -> QuerySet[CourseApplication]:
    """Return all applications for this user on the current site.

    Site isolation is automatic via SiteAwareManager. With no terminal states
    yet, this returns all of the user's applications; it narrows to active states
    once withdraw/approve/reject exist.
    """
    from freedom_ls.course_applications.models import CourseApplication

    return CourseApplication.objects.filter(user=user).select_related("course")
