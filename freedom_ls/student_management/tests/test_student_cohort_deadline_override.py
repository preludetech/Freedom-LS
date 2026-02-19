import pytest
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from freedom_ls.content_engine.models import Topic
from freedom_ls.student_management.models import StudentCohortDeadlineOverride


@pytest.mark.django_db
def test_create_override_with_content_item(
    mock_site_context, cohort_course_reg, student, cohort_membership, topic
):
    """Override can be created for a student in the cohort with a content item."""
    topic_ct = ContentType.objects.get_for_model(Topic)
    deadline_dt = timezone.now() + timezone.timedelta(days=7)

    override = StudentCohortDeadlineOverride.objects.create(
        cohort_course_registration=cohort_course_reg,
        student=student,
        content_type=topic_ct,
        object_id=topic.id,
        deadline=deadline_dt,
    )

    assert override.cohort_course_registration == cohort_course_reg
    assert override.student == student
    assert override.content_item == topic
    assert override.is_hard_deadline is True


@pytest.mark.django_db
def test_create_override_for_whole_course(
    mock_site_context, cohort_course_reg, student, cohort_membership
):
    """Override with null content_item applies to the whole course."""
    override = StudentCohortDeadlineOverride.objects.create(
        cohort_course_registration=cohort_course_reg,
        student=student,
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    assert override.content_item is None


@pytest.mark.django_db
def test_str_with_content_item(
    mock_site_context, cohort_course_reg, student, cohort_membership, topic
):
    """__str__ includes student, cohort, and content item."""
    topic_ct = ContentType.objects.get_for_model(Topic)
    override = StudentCohortDeadlineOverride.objects.create(
        cohort_course_registration=cohort_course_reg,
        student=student,
        content_type=topic_ct,
        object_id=topic.id,
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    result = str(override)
    assert "Test Cohort" in result
    assert "Test Topic" in result


@pytest.mark.django_db
def test_str_without_content_item(
    mock_site_context, cohort_course_reg, student, cohort_membership
):
    """__str__ shows 'Whole course' when content_item is null."""
    override = StudentCohortDeadlineOverride.objects.create(
        cohort_course_registration=cohort_course_reg,
        student=student,
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    assert "Whole course" in str(override)


@pytest.mark.django_db
def test_unique_constraint_prevents_duplicate_item_override(
    mock_site_context, cohort_course_reg, student, cohort_membership, topic
):
    """Cannot create two overrides for the same student + content item."""
    topic_ct = ContentType.objects.get_for_model(Topic)
    StudentCohortDeadlineOverride.objects.create(
        cohort_course_registration=cohort_course_reg,
        student=student,
        content_type=topic_ct,
        object_id=topic.id,
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    with pytest.raises(IntegrityError):
        StudentCohortDeadlineOverride.objects.create(
            cohort_course_registration=cohort_course_reg,
            student=student,
            content_type=topic_ct,
            object_id=topic.id,
            deadline=timezone.now() + timezone.timedelta(days=14),
        )


@pytest.mark.django_db
def test_clean_prevents_duplicate_course_level_override(
    mock_site_context, cohort_course_reg, student, cohort_membership
):
    """clean() raises ValidationError for duplicate course-level overrides."""
    StudentCohortDeadlineOverride.objects.create(
        cohort_course_registration=cohort_course_reg,
        student=student,
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    duplicate = StudentCohortDeadlineOverride(
        cohort_course_registration=cohort_course_reg,
        student=student,
        deadline=timezone.now() + timezone.timedelta(days=14),
    )

    with pytest.raises(ValidationError):
        duplicate.clean()


@pytest.mark.django_db
def test_clean_validates_student_in_cohort(
    mock_site_context, cohort_course_reg, student
):
    """clean() raises ValidationError if student is not a member of the cohort."""
    # student is NOT in the cohort (no cohort_membership fixture)
    override = StudentCohortDeadlineOverride(
        cohort_course_registration=cohort_course_reg,
        student=student,
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    with pytest.raises(ValidationError, match="not a member"):
        override.clean()
