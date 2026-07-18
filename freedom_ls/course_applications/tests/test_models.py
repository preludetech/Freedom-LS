"""Tests for the CourseApplication model."""

from __future__ import annotations

import pytest

from django.db import IntegrityError

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.factories import CourseApplicationFactory


@pytest.mark.django_db
class TestCourseApplicationUniqueConstraint:
    """Unique constraint per (site, user, course)."""

    def test_second_application_same_site_user_course_raises_integrity_error(
        self, mock_site_context
    ):
        """A second CourseApplication for the same (site, user, course) must raise IntegrityError."""
        user = UserFactory()
        course = CourseFactory()
        CourseApplicationFactory(user=user, course=course)

        with pytest.raises(IntegrityError):
            CourseApplicationFactory(user=user, course=course)

    def test_different_users_can_apply_to_same_course(self, mock_site_context):
        """Different users may each have one application for the same course."""
        course = CourseFactory()
        user_a = UserFactory()
        user_b = UserFactory()
        app_a = CourseApplicationFactory(user=user_a, course=course)
        app_b = CourseApplicationFactory(user=user_b, course=course)
        assert app_a.pk != app_b.pk

    def test_same_user_can_apply_to_different_courses(self, mock_site_context):
        """The same user may have one application per course (not a global unique)."""
        user = UserFactory()
        course_a = CourseFactory()
        course_b = CourseFactory()
        app_a = CourseApplicationFactory(user=user, course=course_a)
        app_b = CourseApplicationFactory(user=user, course=course_b)
        assert app_a.pk != app_b.pk
