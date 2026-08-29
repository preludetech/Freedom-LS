import pytest

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from freedom_ls.content_engine.factories import TopicFactory
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCohortDeadlineOverrideFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    CohortMembership,
    LearnerCohortDeadlineOverride,
)


@pytest.mark.django_db
def test_content_item_is_stored_as_a_generic_reference(mock_site_context):
    """`content_item` is a GenericForeignKey: it writes both halves of the pair."""
    topic = TopicFactory()
    cohort = CohortFactory()
    membership: CohortMembership = CohortMembershipFactory(cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort)

    override: LearnerCohortDeadlineOverride = LearnerCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        learner=membership.learner,
        content_item=topic,
    )

    assert override.content_type == ContentType.objects.get_for_model(topic)
    assert override.object_id == topic.pk


@pytest.mark.django_db
def test_str_with_content_item(mock_site_context):
    """__str__ includes learner, cohort, and content item."""
    topic = TopicFactory(title="Test Topic")
    cohort = CohortFactory(name="Test Cohort")
    membership: CohortMembership = CohortMembershipFactory(cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort)

    override = LearnerCohortDeadlineOverrideFactory(
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

    override = LearnerCohortDeadlineOverrideFactory(
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

    LearnerCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        learner=membership.learner,
        content_item=topic,
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    with pytest.raises(IntegrityError):
        LearnerCohortDeadlineOverrideFactory(
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

    LearnerCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        learner=membership.learner,
    )

    duplicate = LearnerCohortDeadlineOverride(
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
    override = LearnerCohortDeadlineOverride(
        cohort_course_registration=cohort_course_reg,
        learner=learner,
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    with pytest.raises(ValidationError, match="not a member"):
        override.clean()


@pytest.mark.django_db
def test_clean_does_not_raise_when_learner_is_unset(mock_site_context):
    """An unset learner means a field-level error already exists (an invalid
    choice in the admin inline); clean() must let that surface rather than
    crashing on the missing relation."""
    override = LearnerCohortDeadlineOverride(
        cohort_course_registration=CohortCourseRegistrationFactory(),
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    override.clean()


@pytest.mark.django_db
def test_clean_does_not_raise_when_the_registration_is_unset(mock_site_context):
    override = LearnerCohortDeadlineOverride(
        learner=LearnerFactory(),
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    override.clean()
