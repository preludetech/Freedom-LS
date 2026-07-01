"""Tests for the CourseInterest model's unique (user, course) constraint."""

from __future__ import annotations

import pytest

from django.db import IntegrityError

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_interest.factories import CourseInterestFactory


@pytest.mark.django_db
class TestCourseInterestUniqueConstraint:
    """The unique constraint rejects a duplicate (user, course) pair."""

    def test_duplicate_user_course_raises_integrity_error(self, mock_site_context):
        """A second CourseInterest for the same (user, course) must raise IntegrityError."""
        user = UserFactory()
        course = CourseFactory()
        CourseInterestFactory(user=user, course=course)

        with pytest.raises(IntegrityError):
            CourseInterestFactory(user=user, course=course)

    def test_different_users_can_express_interest_in_same_course(
        self, mock_site_context
    ):
        """Different users may each express interest in the same course."""
        course = CourseFactory()
        user_a = UserFactory()
        user_b = UserFactory()
        interest_a = CourseInterestFactory(user=user_a, course=course)
        interest_b = CourseInterestFactory(user=user_b, course=course)
        assert interest_a.pk != interest_b.pk

    def test_same_user_can_express_interest_in_different_courses(
        self, mock_site_context
    ):
        """The same user may express interest in multiple courses."""
        user = UserFactory()
        course_a = CourseFactory()
        course_b = CourseFactory()
        interest_a = CourseInterestFactory(user=user, course=course_a)
        interest_b = CourseInterestFactory(user=user, course=course_b)
        assert interest_a.pk != interest_b.pk
