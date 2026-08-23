import pytest

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from freedom_ls.content_engine.factories import TopicFactory
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
    UserCohortDeadlineOverrideFactory,
)
from freedom_ls.learner_management.models import (
    CohortMembership,
    UserCohortDeadlineOverride,
)


@pytest.mark.django_db
def test_create_override_with_content_item(mock_site_context):
    """Override can be created for a user in the cohort with a content item."""
    topic = TopicFactory()
    cohort = CohortFactory()
    membership: CohortMembership = CohortMembershipFactory(cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort)

    deadline_dt = timezone.now() + timezone.timedelta(days=7)

    override: UserCohortDeadlineOverride = UserCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        learner=membership.learner,
        content_item=topic,
        deadline=deadline_dt,
        is_hard_deadline=True,
    )

    assert override.cohort_course_registration == cohort_course_reg
    assert override.learner == membership.learner
    assert override.content_item == topic
    assert override.is_hard_deadline is True


@pytest.mark.django_db
def test_create_override_for_whole_course(mock_site_context):
    """Override with null content_item applies to the whole course."""
    cohort = CohortFactory()
    membership: CohortMembership = CohortMembershipFactory(cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort)

    override: UserCohortDeadlineOverride = UserCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        learner=membership.learner,
    )

    assert override.content_item is None


@pytest.mark.django_db
def test_str_with_content_item(mock_site_context):
    """__str__ includes learner, cohort, and content item."""
    topic = TopicFactory(title="Test Topic")
    cohort = CohortFactory(name="Test Cohort")
    membership: CohortMembership = CohortMembershipFactory(cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort)

    override = UserCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        learner=membership.learner,
        content_item=topic,
    )

    result = str(override)
    assert "Test Cohort" in result
    assert "Test Topic" in result


@pytest.mark.django_db
def test_str_without_content_item(mock_site_context):
    """__str__ shows 'Whole course' when content_item is null."""
    cohort = CohortFactory(name="Test Cohort")
    membership: CohortMembership = CohortMembershipFactory(cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort)

    override = UserCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        learner=membership.learner,
    )

    assert "Whole course" in str(override)


@pytest.mark.django_db
def test_unique_constraint_prevents_duplicate_item_override(mock_site_context):
    """Cannot create two overrides for the same learner + content item."""
    topic = TopicFactory()
    cohort = CohortFactory()
    membership: CohortMembership = CohortMembershipFactory(cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort)

    UserCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        learner=membership.learner,
        content_item=topic,
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    with pytest.raises(IntegrityError):
        UserCohortDeadlineOverrideFactory(
            cohort_course_registration=cohort_course_reg,
            learner=membership.learner,
            content_item=topic,
            deadline=timezone.now() + timezone.timedelta(days=14),
        )


@pytest.mark.django_db
def test_clean_prevents_duplicate_course_level_override(mock_site_context):
    """clean() raises ValidationError for duplicate course-level overrides."""
    cohort = CohortFactory()
    membership: CohortMembership = CohortMembershipFactory(cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort)

    UserCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        learner=membership.learner,
    )

    duplicate = UserCohortDeadlineOverride(
        cohort_course_registration=cohort_course_reg,
        learner=membership.learner,
        deadline=timezone.now() + timezone.timedelta(days=14),
    )

    with pytest.raises(ValidationError):
        duplicate.clean()


@pytest.mark.django_db
def test_clean_validates_learner_in_cohort(mock_site_context):
    """clean() raises ValidationError if the learner is not a member of the cohort."""
    cohort_course_reg = CohortCourseRegistrationFactory()
    learner = LearnerFactory(organisation=cohort_course_reg.cohort.organisation)

    # learner is NOT in the cohort (no membership created)
    override = UserCohortDeadlineOverride(
        cohort_course_registration=cohort_course_reg,
        learner=learner,
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    with pytest.raises(ValidationError, match="not a member"):
        override.clean()
