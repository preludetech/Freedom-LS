from datetime import timedelta

import pytest

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from freedom_ls.content_engine.factories import TopicFactory
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortDeadlineFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCohortDeadlineOverrideFactory,
    LearnerCourseRegistrationFactory,
    LearnerDeadlineFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    CohortDeadline,
    CohortMembership,
    LearnerCohortDeadlineOverride,
    LearnerDeadline,
)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "factory",
    [
        CohortDeadlineFactory,
        LearnerDeadlineFactory,
        LearnerCohortDeadlineOverrideFactory,
    ],
)
def test_str_names_the_content_item_or_the_whole_course(
    mock_site_context, factory
) -> None:
    topic = TopicFactory(title="Test Topic")

    item_deadline = factory(content_item=topic)
    course_deadline = factory()

    assert "Test Topic" in str(item_deadline)
    assert "Whole course" in str(course_deadline)


@pytest.mark.django_db
def test_create_cohort_deadline_with_content_item(mock_site_context):
    """CohortDeadline can be created pointing to a specific content item."""
    topic = TopicFactory(title="Test Topic")
    cohort_course_reg = CohortCourseRegistrationFactory()

    deadline_dt = timezone.now() + timedelta(days=7)

    deadline: CohortDeadline = CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic,
        deadline=deadline_dt,
        is_hard_deadline=True,
    )

    assert deadline.cohort_course_registration == cohort_course_reg
    assert deadline.content_item == topic
    assert deadline.deadline == deadline_dt
    assert deadline.is_hard_deadline is True


@pytest.mark.django_db
def test_create_cohort_deadline_for_whole_course(mock_site_context):
    """CohortDeadline with null content_item applies to the whole course."""
    cohort_course_reg = CohortCourseRegistrationFactory()
    deadline_dt = timezone.now() + timedelta(days=7)

    deadline: CohortDeadline = CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        deadline=deadline_dt,
    )

    assert deadline.content_type is None
    assert deadline.object_id is None
    assert deadline.content_item is None


@pytest.mark.django_db
def test_cohort_deadline_unique_constraint_prevents_duplicate_item_deadline(
    mock_site_context,
):
    """Cannot create two deadlines for the same content item on the same registration."""
    topic = TopicFactory()
    cohort_course_reg = CohortCourseRegistrationFactory()

    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic,
        deadline=timezone.now() + timedelta(days=7),
    )

    with pytest.raises(IntegrityError):
        CohortDeadlineFactory(
            cohort_course_registration=cohort_course_reg,
            content_item=topic,
            deadline=timezone.now() + timedelta(days=14),
        )


@pytest.mark.django_db
def test_cohort_deadline_clean_prevents_duplicate_course_level_deadline(
    mock_site_context,
):
    """clean() raises ValidationError for duplicate course-level deadlines."""
    cohort_course_reg = CohortCourseRegistrationFactory()

    CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
    )

    duplicate = CohortDeadline(
        cohort_course_registration=cohort_course_reg,
        deadline=timezone.now() + timedelta(days=14),
    )

    with pytest.raises(ValidationError):
        duplicate.clean()


@pytest.mark.django_db
def test_create_learner_deadline_with_content_item(mock_site_context):
    """LearnerDeadline can be created pointing to a specific content item."""
    topic = TopicFactory()
    learner_course_reg = LearnerCourseRegistrationFactory()

    deadline_dt = timezone.now() + timedelta(days=7)

    deadline: LearnerDeadline = LearnerDeadlineFactory(
        learner_course_registration=learner_course_reg,
        content_item=topic,
        deadline=deadline_dt,
        is_hard_deadline=True,
    )

    assert deadline.learner_course_registration == learner_course_reg
    assert deadline.content_item == topic
    assert deadline.is_hard_deadline is True


@pytest.mark.django_db
def test_create_learner_deadline_for_whole_course(mock_site_context):
    """LearnerDeadline with null content_item applies to the whole course."""
    learner_course_reg = LearnerCourseRegistrationFactory()

    deadline: LearnerDeadline = LearnerDeadlineFactory(
        learner_course_registration=learner_course_reg,
    )

    assert deadline.content_item is None


@pytest.mark.django_db
def test_learner_deadline_unique_constraint_prevents_duplicate_item_deadline(
    mock_site_context,
):
    """Cannot create two deadlines for the same content item on the same registration."""
    topic = TopicFactory()
    learner_course_reg = LearnerCourseRegistrationFactory()

    LearnerDeadlineFactory(
        learner_course_registration=learner_course_reg,
        content_item=topic,
        deadline=timezone.now() + timedelta(days=7),
    )

    with pytest.raises(IntegrityError):
        LearnerDeadlineFactory(
            learner_course_registration=learner_course_reg,
            content_item=topic,
            deadline=timezone.now() + timedelta(days=14),
        )


@pytest.mark.django_db
def test_learner_deadline_clean_prevents_duplicate_course_level_deadline(
    mock_site_context,
):
    """clean() raises ValidationError for duplicate course-level deadlines."""
    learner_course_reg = LearnerCourseRegistrationFactory()

    LearnerDeadlineFactory(
        learner_course_registration=learner_course_reg,
    )

    duplicate = LearnerDeadline(
        learner_course_registration=learner_course_reg,
        deadline=timezone.now() + timedelta(days=14),
    )

    with pytest.raises(ValidationError):
        duplicate.clean()


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
        deadline=timezone.now() + timedelta(days=7),
    )

    with pytest.raises(IntegrityError):
        LearnerCohortDeadlineOverrideFactory(
            cohort_course_registration=cohort_course_reg,
            learner=membership.learner,
            content_item=topic,
            deadline=timezone.now() + timedelta(days=14),
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
        deadline=timezone.now() + timedelta(days=14),
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
        deadline=timezone.now() + timedelta(days=7),
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
        deadline=timezone.now() + timedelta(days=7),
    )

    override.clean()


@pytest.mark.django_db
def test_clean_does_not_raise_when_the_registration_is_unset(mock_site_context):
    override = LearnerCohortDeadlineOverride(
        learner=LearnerFactory(),
        deadline=timezone.now() + timedelta(days=7),
    )

    override.clean()
