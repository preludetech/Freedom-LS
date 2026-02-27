import pytest
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from freedom_ls.content_engine.factories import TopicFactory
from freedom_ls.student_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    StudentCohortDeadlineOverrideFactory,
    StudentFactory,
)
from freedom_ls.student_management.models import StudentCohortDeadlineOverride


@pytest.mark.django_db
def test_create_override_with_content_item(mock_site_context):
    """Override can be created for a student in the cohort with a content item."""
    topic = TopicFactory()
    student = StudentFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(student=student, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort)

    deadline_dt = timezone.now() + timezone.timedelta(days=7)

    override = StudentCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        student=student,
        content_item=topic,
        deadline=deadline_dt,
        is_hard_deadline=True,
    )

    assert override.cohort_course_registration == cohort_course_reg
    assert override.student == student
    assert override.content_item == topic
    assert override.is_hard_deadline is True


@pytest.mark.django_db
def test_create_override_for_whole_course(mock_site_context):
    """Override with null content_item applies to the whole course."""
    student = StudentFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(student=student, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort)

    override = StudentCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        student=student,
    )

    assert override.content_item is None


@pytest.mark.django_db
def test_str_with_content_item(mock_site_context):
    """__str__ includes student, cohort, and content item."""
    topic = TopicFactory(title="Test Topic")
    cohort = CohortFactory(name="Test Cohort")
    student = StudentFactory()
    CohortMembershipFactory(student=student, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort)

    override = StudentCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        student=student,
        content_item=topic,
    )

    result = str(override)
    assert "Test Cohort" in result
    assert "Test Topic" in result


@pytest.mark.django_db
def test_str_without_content_item(mock_site_context):
    """__str__ shows 'Whole course' when content_item is null."""
    cohort = CohortFactory(name="Test Cohort")
    student = StudentFactory()
    CohortMembershipFactory(student=student, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort)

    override = StudentCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        student=student,
    )

    assert "Whole course" in str(override)


@pytest.mark.django_db
def test_unique_constraint_prevents_duplicate_item_override(mock_site_context):
    """Cannot create two overrides for the same student + content item."""
    topic = TopicFactory()
    student = StudentFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(student=student, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort)

    StudentCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        student=student,
        content_item=topic,
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    with pytest.raises(IntegrityError):
        StudentCohortDeadlineOverrideFactory(
            cohort_course_registration=cohort_course_reg,
            student=student,
            content_item=topic,
            deadline=timezone.now() + timezone.timedelta(days=14),
        )


@pytest.mark.django_db
def test_clean_prevents_duplicate_course_level_override(mock_site_context):
    """clean() raises ValidationError for duplicate course-level overrides."""
    student = StudentFactory()
    cohort = CohortFactory()
    CohortMembershipFactory(student=student, cohort=cohort)
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort)

    StudentCohortDeadlineOverrideFactory(
        cohort_course_registration=cohort_course_reg,
        student=student,
    )

    duplicate = StudentCohortDeadlineOverride(
        cohort_course_registration=cohort_course_reg,
        student=student,
        deadline=timezone.now() + timezone.timedelta(days=14),
    )

    with pytest.raises(ValidationError):
        duplicate.clean()


@pytest.mark.django_db
def test_clean_validates_student_in_cohort(mock_site_context):
    """clean() raises ValidationError if student is not a member of the cohort."""
    student = StudentFactory()
    cohort_course_reg = CohortCourseRegistrationFactory()

    # student is NOT in the cohort (no membership created)
    override = StudentCohortDeadlineOverride(
        cohort_course_registration=cohort_course_reg,
        student=student,
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    with pytest.raises(ValidationError, match="not a member"):
        override.clean()
