"""Tests for course_applications query helpers."""

from __future__ import annotations

import pytest

from django.contrib.auth.models import AnonymousUser

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

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

    def test_anonymous_user_returns_none_with_no_query(
        self, mock_site_context, django_assert_num_queries
    ):
        """Anonymous user returns None immediately without hitting the database."""
        from freedom_ls.course_applications.queries import get_application_for_course

        course = CourseFactory()

        with django_assert_num_queries(0):
            result = get_application_for_course(user=AnonymousUser(), course=course)

        assert result is None


@pytest.mark.django_db
class TestGetActiveApplications:
    """get_active_applications returns the user's applications."""

    def test_anonymous_user_returns_empty_queryset_with_no_query(
        self, mock_site_context, django_assert_num_queries
    ):
        """Anonymous user returns an empty queryset without hitting the database."""
        from freedom_ls.course_applications.queries import get_active_applications

        with django_assert_num_queries(0):
            result = list(get_active_applications(AnonymousUser()))

        assert result == []
