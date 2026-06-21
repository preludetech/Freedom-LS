"""Tests for student_management.utils.is_registered_for_course (Task A.5 extraction).

TDD: tests written first (red), then implementation added (green).
"""

from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.student_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    UserCourseRegistrationFactory,
)


@pytest.mark.django_db
class TestIsRegisteredForCourse:
    """Tests for student_management.utils.is_registered_for_course."""

    def test_anonymous_user_is_not_registered(self, mock_site_context):
        from django.contrib.auth.models import AnonymousUser

        from freedom_ls.student_management.utils import is_registered_for_course

        course = CourseFactory()
        assert is_registered_for_course(AnonymousUser(), course) is False

    def test_directly_registered_user_is_registered(self, mock_site_context):
        from freedom_ls.student_management.utils import is_registered_for_course

        course = CourseFactory()
        user = UserFactory()
        UserCourseRegistrationFactory(user=user, collection=course, is_active=True)
        assert is_registered_for_course(user, course) is True

    def test_inactive_direct_registration_is_not_registered(self, mock_site_context):
        from freedom_ls.student_management.utils import is_registered_for_course

        course = CourseFactory()
        user = UserFactory()
        UserCourseRegistrationFactory(user=user, collection=course, is_active=False)
        assert is_registered_for_course(user, course) is False

    def test_cohort_registered_user_is_registered(self, mock_site_context):
        from freedom_ls.student_management.utils import is_registered_for_course

        course = CourseFactory()
        user = UserFactory()
        cohort = CohortFactory()
        CohortMembershipFactory(user=user, cohort=cohort)
        CohortCourseRegistrationFactory(
            cohort=cohort, collection=course, is_active=True
        )
        assert is_registered_for_course(user, course) is True

    def test_user_not_registered_at_all_returns_false(self, mock_site_context):
        from freedom_ls.student_management.utils import is_registered_for_course

        course = CourseFactory()
        user = UserFactory()
        assert is_registered_for_course(user, course) is False
