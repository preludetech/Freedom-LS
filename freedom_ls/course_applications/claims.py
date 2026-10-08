"""Which unclaimed applications a browser holds.

An unclaimed application has no owner yet, so the only proof a visitor may
see it is that their session remembers its id.
"""

from __future__ import annotations

from django.http import HttpRequest

from freedom_ls.content_engine.models import Course
from freedom_ls.course_applications.models import CourseApplication

UNCLAIMED_APPLICATIONS_SESSION_KEY = "course_applications_unclaimed_ids"


def unclaimed_application_ids(request: HttpRequest) -> list[str]:
    """The ids this browser may still claim. Strings, because the session is JSON."""
    ids: list[str] = request.session.get(UNCLAIMED_APPLICATIONS_SESSION_KEY, [])
    return list(ids)


def remember_unclaimed_application(
    request: HttpRequest, application: CourseApplication
) -> None:
    # Reassigned rather than appended in place: the session only notices a
    # change when the key is set.
    ids = unclaimed_application_ids(request)
    if str(application.pk) not in ids:
        request.session[UNCLAIMED_APPLICATIONS_SESSION_KEY] = [
            *ids,
            str(application.pk),
        ]


def unclaimed_application_for_course(
    request: HttpRequest, course: Course
) -> CourseApplication | None:
    """This browser's unclaimed application to the course, if it holds one."""
    ids = unclaimed_application_ids(request)
    if not ids:
        return None
    return (
        CourseApplication.objects.filter(pk__in=ids, user__isnull=True, course=course)
        .select_related("course", "form_progress__form")
        .first()
    )
