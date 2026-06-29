"""Tests for the CourseInterest model.

TDD: these tests are written before the implementation.
"""

from __future__ import annotations

import pytest

from django.db import IntegrityError

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_interest.factories import CourseInterestFactory
from freedom_ls.course_interest.models import CourseInterest


@pytest.mark.django_db
class TestCourseInterestCreation:
    """A CourseInterest can be created via factory under mock_site_context."""

    def test_course_interest_created_with_factory(self, mock_site_context):
        """A CourseInterest is created successfully via factory."""
        interest = CourseInterestFactory()
        assert interest.pk is not None
        assert interest.user is not None
        assert interest.course is not None

    def test_course_interest_has_created_at(self, mock_site_context):
        """A CourseInterest has a created_at timestamp set automatically."""
        interest = CourseInterestFactory()
        assert interest.created_at is not None


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


@pytest.mark.django_db
class TestCourseInterestGetOrCreate:
    """get_or_create is idempotent — one row after repeat calls."""

    def test_get_or_create_is_idempotent(self, mock_site_context):
        """Calling get_or_create twice for the same (user, course) produces one row."""
        user = UserFactory()
        course = CourseFactory()

        interest_1, created_1 = CourseInterest.objects.get_or_create(
            user=user, course=course
        )
        interest_2, created_2 = CourseInterest.objects.get_or_create(
            user=user, course=course
        )

        assert created_1 is True
        assert created_2 is False
        assert interest_1.pk == interest_2.pk
        assert CourseInterest.objects.filter(user=user, course=course).count() == 1
