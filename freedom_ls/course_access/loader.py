"""Loader for the active course-access backend (Task A.4).

get_course_access_backend() is cached for the process lifetime. Callers that use
override_settings(COURSE_ACCESS_BACKEND=...) in tests MUST call
get_course_access_backend.cache_clear() before and after the test to avoid the
cached instance bleeding across tests.
"""

from __future__ import annotations

import functools
from typing import Any

from django.conf import settings
from django.utils.module_loading import import_string

from freedom_ls.course_access.backends import CourseAccessBackend


@functools.cache
def get_course_access_backend() -> CourseAccessBackend:
    """Return the configured course-access backend (cached for the process lifetime).

    Resolves settings.COURSE_ACCESS_BACKEND via import_string and instantiates it.

    Test caveat: callers using override_settings(COURSE_ACCESS_BACKEND=...) must call
    get_course_access_backend.cache_clear() before and after the test so that the
    overridden setting takes effect and the cache is restored afterward.
    """
    backend_class: type[CourseAccessBackend] = import_string(
        settings.COURSE_ACCESS_BACKEND
    )
    return backend_class()


def validate_course_access_config(
    # Deliberate Any: access_config is a genuinely opaque JSON blob whose keys are
    # backend-owned; this delegator never inspects them.
    raw: dict[str, Any],
    *,
    file_path: str = "",
) -> dict[str, Any]:
    """Hook target for content_engine's COURSE_ACCESS_CONFIG_VALIDATOR setting.

    Delegates to the active backend's single validate_course_config() — no
    duplicate validation logic lives here. content_engine resolves this function
    via import_string(settings.COURSE_ACCESS_CONFIG_VALIDATOR) so that
    content_engine never imports course_access directly (avoiding a dependency cycle).
    """
    return get_course_access_backend().validate_course_config(raw, file_path=file_path)
