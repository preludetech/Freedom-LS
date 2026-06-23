"""Tests for course_applications query helpers."""

from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_applications.factories import CourseApplicationFactory


@pytest.mark.django_db
class TestGetApplicationForCourse:
    """get_application_for_course returns the user's application or None."""

    def test_returns_application_when_present(self, mock_site_context):
        """Returns the application when the user has applied to the course."""
        from freedom_ls.course_applications.queries import get_application_for_course

        user = UserFactory()
        course = CourseFactory()
        app = CourseApplicationFactory(user=user, course=course)

        assert get_application_for_course(user=user, course=course) == app

    def test_returns_none_when_absent(self, mock_site_context):
        """Returns None when the user has no application to the course."""
        from freedom_ls.course_applications.queries import get_application_for_course

        user = UserFactory()
        course = CourseFactory()

        assert get_application_for_course(user=user, course=course) is None
