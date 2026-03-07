import pytest

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import TopicFactory
from freedom_ls.student_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    UserCohortDeadlineOverrideFactory,
)
from freedom_ls.student_management.models import UserCohortDeadlineOverride


@pytest.mark.django_db
def test_create_override_with_content_item(mock_site_context):
    """Override can be created for a user in the cohort with a content item."""
    topic = TopicFactory()
    user = UserFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(user=user, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort)

    deadline_dt = timezone.now() + timezone.timedelta(days=7)

    override: UserCohortDeadlineOverride = UserCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        user=user,
        content_item=topic,
        deadline=deadline_dt,
        is_hard_deadline=True,
    )

    assert override.cohort_course_registration == cohort_course_reg
    assert override.user == user
    assert override.content_item == topic
    assert override.is_hard_deadline is True


@pytest.mark.django_db
def test_create_override_for_whole_course(mock_site_context):
    """Override with null content_item applies to the whole course."""
    user = UserFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(user=user, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort)

    override: UserCohortDeadlineOverride = UserCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        user=user,
    )

    assert override.content_item is None


@pytest.mark.django_db
def test_str_with_content_item(mock_site_context):
    """__str__ includes user, cohort, and content item."""
    topic = TopicFactory(title="Test Topic")
    cohort = CohortFactory(name="Test Cohort")
    user = UserFactory()
    CohortMembershipFactory(user=user, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort)

    override = UserCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        user=user,
        content_item=topic,
    )

    result = str(override)
    assert "Test Cohort" in result
    assert "Test Topic" in result


@pytest.mark.django_db
def test_str_without_content_item(mock_site_context):
    """__str__ shows 'Whole course' when content_item is null."""
    cohort = CohortFactory(name="Test Cohort")
    user = UserFactory()
    CohortMembershipFactory(user=user, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort)

    override = UserCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        user=user,
    )

    assert "Whole course" in str(override)


@pytest.mark.django_db
def test_unique_constraint_prevents_duplicate_item_override(mock_site_context):
    """Cannot create two overrides for the same user + content item."""
    topic = TopicFactory()
    user = UserFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(user=user, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort)

    UserCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        user=user,
        content_item=topic,
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    with pytest.raises(IntegrityError):
        UserCohortDeadlineOverrideFactory(
            cohort_course_registration=cohort_course_reg,
            user=user,
            content_item=topic,
            deadline=timezone.now() + timezone.timedelta(days=14),
        )


@pytest.mark.django_db
def test_clean_prevents_duplicate_course_level_override(mock_site_context):
    """clean() raises ValidationError for duplicate course-level overrides."""
    user = UserFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(user=user, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort)

    UserCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        user=user,
    )

    duplicate = UserCohortDeadlineOverride(
        cohort_course_registration=cohort_course_reg,
        user=user,
        deadline=timezone.now() + timezone.timedelta(days=14),
    )

    with pytest.raises(ValidationError):
        duplicate.clean()


@pytest.mark.django_db
def test_clean_validates_user_in_cohort(mock_site_context):
    """clean() raises ValidationError if user is not a member of the cohort."""
    user = UserFactory()
    cohort_course_reg = CohortCourseRegistrationFactory()

    # user is NOT in the cohort (no membership created)
    override = UserCohortDeadlineOverride(
        cohort_course_registration=cohort_course_reg,
        user=user,
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    with pytest.raises(ValidationError, match="not a member"):
        override.clean()
