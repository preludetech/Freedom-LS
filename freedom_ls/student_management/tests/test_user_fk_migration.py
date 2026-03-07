"""Tests that the user FK is non-nullable on affected models."""

import pytest

from freedom_ls.student_management.models import (
    CohortMembership,
    UserCohortDeadlineOverride,
    UserCourseRegistration,
)


@pytest.mark.django_db
class TestUserFKExists:
    """Verify the user field exists and is non-nullable on each affected model."""

    def test_cohort_membership_has_non_nullable_user_field(self):
        field = CohortMembership._meta.get_field("user")
        assert field.null is False

    def test_user_course_registration_has_non_nullable_user_field(self):
        field = UserCourseRegistration._meta.get_field("user")
        assert field.null is False

    def test_user_cohort_deadline_override_has_non_nullable_user_field(self):
        field = UserCohortDeadlineOverride._meta.get_field("user")
        assert field.null is False
