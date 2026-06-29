"""Tests for course_interest queries (Task 3.1).

TDD: these tests are written before the implementation.
"""

from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.course_interest.factories import CourseInterestFactory
from freedom_ls.course_interest.queries import get_interested_course_ids


@pytest.mark.django_db
class TestGetInterestedCourseIds:
    """get_interested_course_ids returns the set of course IDs the user has expressed interest in."""

    def test_returns_ids_of_interested_courses(self, mock_site_context):
        """Returns a set containing the course IDs the user expressed interest in."""
        user = UserFactory()
        course_a = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        course_b = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        CourseInterestFactory(user=user, course=course_a)

        from freedom_ls.content_engine.models import Course

        courses = Course.objects.filter(pk__in=[course_a.pk, course_b.pk])
        result = get_interested_course_ids(user, courses)

        assert course_a.pk in result
        assert course_b.pk not in result

    def test_returns_empty_set_for_unauthenticated_user(self, mock_site_context):
        """Returns an empty set for an anonymous (unauthenticated) user."""
        from django.contrib.auth.models import AnonymousUser

        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)

        from freedom_ls.content_engine.models import Course

        courses = Course.objects.filter(pk=course.pk)
        result = get_interested_course_ids(AnonymousUser(), courses)

        assert result == set()

    def test_returns_empty_set_when_no_interest(self, mock_site_context):
        """Returns an empty set when the user has no interest in any of the given courses."""
        user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)

        from freedom_ls.content_engine.models import Course

        courses = Course.objects.filter(pk=course.pk)
        result = get_interested_course_ids(user, courses)

        assert result == set()

    def test_returns_only_own_interests(self, mock_site_context):
        """Returns only the IDs of courses the given user expressed interest in, not others."""
        user = UserFactory()
        other_user = UserFactory()
        course = CourseFactory(visibility=CourseVisibility.COMING_SOON)
        CourseInterestFactory(user=other_user, course=course)

        from freedom_ls.content_engine.models import Course

        courses = Course.objects.filter(pk=course.pk)
        result = get_interested_course_ids(user, courses)

        assert course.pk not in result
