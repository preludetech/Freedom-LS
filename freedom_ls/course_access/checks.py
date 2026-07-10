"""Django system checks for the course_access app.

Check IDs follow Django's convention: ``app_label.severity + number``.
E = Error. Checks run automatically on runserver, migrate, test,
and ``manage.py check``.

E001 — Either COURSE_ACCESS_BACKEND is unset (required), or a Course has an
       access_config that the active backend rejects. The two never fire in the
       same run: an unset backend short-circuits before any Course is checked.
       The latter surfaces config invalidated by a COURSE_ACCESS_BACKEND swap
       at manage.py check time.
"""

from __future__ import annotations

from collections.abc import Sequence

from django.apps import AppConfig
from django.core.checks import CheckMessage, Error, register

from freedom_ls.base.app_settings import required_settings_errors


@register()
def check_course_access_configs(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[CheckMessage]:
    """E001: Check that every Course.access_config is valid for the active backend.

    Uses local imports inside the function to avoid touching the app registry
    or DB at import time. Wraps DB access in try/except so that a fresh
    checkout (tables not yet migrated) stays silent rather than crashing.
    """
    from django.db.utils import DatabaseError, OperationalError, ProgrammingError

    from freedom_ls.content_engine.models import Course
    from freedom_ls.course_access.config import config
    from freedom_ls.course_access.loader import get_course_access_backend

    if config.missing_required():
        # COURSE_ACCESS_BACKEND is unset: the loader below would raise
        # ImproperlyConfigured. Report the missing setting instead of crashing
        # (or silently passing) manage.py check.
        return required_settings_errors(config, "freedom_ls_course_access")

    errors: list[CheckMessage] = []

    try:
        backend = get_course_access_backend()
        courses = list(Course.objects.only("slug", "access_config"))
    except (DatabaseError, OperationalError, ProgrammingError):
        # Tables not ready (initial migrate, fresh checkout, etc.) — stay silent.
        return []

    for course in courses:
        try:
            backend.validate_course_config(course.access_config)
        except ValueError as exc:
            errors.append(
                Error(
                    f"Course {course.slug!r} has an invalid access_config: {exc}",
                    hint=(
                        "Check COURSE_ACCESS_BACKEND and the course's access_config. "
                        "This can happen after swapping the backend to one that does not "
                        "recognise the previously-stored access_type."
                    ),
                    id="freedom_ls_course_access.E001",
                )
            )

    return errors
