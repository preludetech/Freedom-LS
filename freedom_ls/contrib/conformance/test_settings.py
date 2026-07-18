"""Behavioural probe for the configured course-access backend.

Presence/value checks for COURSE_ACCESS_BACKEND live in system checks, not
here — this probe exercises the loader end-to-end, which a static check
cannot do.
"""

from __future__ import annotations

import pytest

from django.apps import apps

__all__ = ["test_configured_backend_instantiates"]

_COURSE_ACCESS_BACKEND_CONSUMERS: tuple[str, ...] = (
    "freedom_ls.student_interface",
    "freedom_ls.course_applications",
)


def test_configured_backend_instantiates() -> None:
    if not any(apps.is_installed(app) for app in _COURSE_ACCESS_BACKEND_CONSUMERS):
        pytest.skip("no COURSE_ACCESS_BACKEND consumer installed")
    from freedom_ls.course_access.backends import CourseAccessBackend
    from freedom_ls.course_access.loader import get_course_access_backend

    backend = get_course_access_backend()
    assert isinstance(backend, CourseAccessBackend)
