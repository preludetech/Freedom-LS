"""Tests for the session half of the claims module."""

from __future__ import annotations

import pytest

from django.contrib.sessions.backends.db import SessionStore
from django.http import HttpRequest

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.claims import (
    UNCLAIMED_APPLICATIONS_SESSION_KEY,
    remember_unclaimed_application,
    unclaimed_application_for_course,
)
from freedom_ls.course_applications.factories import CourseApplicationFactory


def _request() -> HttpRequest:
    request = HttpRequest()
    request.session = SessionStore()
    return request


@pytest.mark.django_db
class TestClaims:
    def test_remember_stores_the_pk_as_a_string(self, mock_site_context):
        request = _request()
        app = CourseApplicationFactory(unclaimed=True)

        remember_unclaimed_application(request, app)

        assert request.session[UNCLAIMED_APPLICATIONS_SESSION_KEY] == [str(app.pk)]

    def test_remember_reassigns_the_list(self, mock_site_context):
        request = _request()
        remember_unclaimed_application(
            request, CourseApplicationFactory(unclaimed=True)
        )
        request.session.modified = False

        remember_unclaimed_application(
            request, CourseApplicationFactory(unclaimed=True)
        )

        assert request.session.modified is True

    def test_unclaimed_application_for_course_finds_a_remembered_row(
        self, mock_site_context
    ):
        request = _request()
        app = CourseApplicationFactory(unclaimed=True)
        remember_unclaimed_application(request, app)

        assert unclaimed_application_for_course(request, app.course) == app

    def test_unclaimed_application_for_course_ignores_a_claimed_row(
        self, mock_site_context
    ):
        request = _request()
        app = CourseApplicationFactory()
        remember_unclaimed_application(request, app)

        assert unclaimed_application_for_course(request, app.course) is None

    def test_unclaimed_application_for_course_ignores_another_course(
        self, mock_site_context
    ):
        request = _request()
        app = CourseApplicationFactory(unclaimed=True)
        remember_unclaimed_application(request, app)

        assert unclaimed_application_for_course(request, CourseFactory()) is None
