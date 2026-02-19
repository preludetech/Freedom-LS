import pytest
from django.utils import timezone
from freedom_ls.content_engine.models import Topic
from freedom_ls.student_management.models import CohortDeadline


@pytest.mark.django_db
def test_create_cohort_deadline_with_content_item(
    mock_site_context, cohort_course_reg, topic
):
    """CohortDeadline can be created pointing to a specific content item."""
    from django.contrib.contenttypes.models import ContentType

    topic_ct = ContentType.objects.get_for_model(Topic)
    deadline_dt = timezone.now() + timezone.timedelta(days=7)

    deadline = CohortDeadline.objects.create(
        cohort_course_registration=cohort_course_reg,
        content_type=topic_ct,
        object_id=topic.id,
        deadline=deadline_dt,
    )

    assert deadline.cohort_course_registration == cohort_course_reg
    assert deadline.content_type == topic_ct
    assert deadline.object_id == topic.id
    assert deadline.content_item == topic
    assert deadline.deadline == deadline_dt
    assert deadline.is_hard_deadline is True


@pytest.mark.django_db
def test_create_cohort_deadline_for_whole_course(mock_site_context, cohort_course_reg):
    """CohortDeadline with null content_item applies to the whole course."""
    deadline_dt = timezone.now() + timezone.timedelta(days=7)

    deadline = CohortDeadline.objects.create(
        cohort_course_registration=cohort_course_reg,
        content_type=None,
        object_id=None,
        deadline=deadline_dt,
    )

    assert deadline.content_type is None
    assert deadline.object_id is None
    assert deadline.content_item is None


@pytest.mark.django_db
def test_str_with_content_item(mock_site_context, cohort_course_reg, topic):
    """__str__ includes the content item name."""
    from django.contrib.contenttypes.models import ContentType

    topic_ct = ContentType.objects.get_for_model(Topic)
    deadline = CohortDeadline.objects.create(
        cohort_course_registration=cohort_course_reg,
        content_type=topic_ct,
        object_id=topic.id,
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    assert str(deadline) == "Test Cohort - Test Course - Test Topic"


@pytest.mark.django_db
def test_str_without_content_item(mock_site_context, cohort_course_reg):
    """__str__ shows 'Whole course' when content_item is null."""
    deadline = CohortDeadline.objects.create(
        cohort_course_registration=cohort_course_reg,
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    assert str(deadline) == "Test Cohort - Test Course - Whole course"


@pytest.mark.django_db
def test_unique_constraint_prevents_duplicate_item_deadline(
    mock_site_context, cohort_course_reg, topic
):
    """Cannot create two deadlines for the same content item on the same registration."""
    from django.contrib.contenttypes.models import ContentType
    from django.db import IntegrityError

    topic_ct = ContentType.objects.get_for_model(Topic)
    CohortDeadline.objects.create(
        cohort_course_registration=cohort_course_reg,
        content_type=topic_ct,
        object_id=topic.id,
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    with pytest.raises(IntegrityError):
        CohortDeadline.objects.create(
            cohort_course_registration=cohort_course_reg,
            content_type=topic_ct,
            object_id=topic.id,
            deadline=timezone.now() + timezone.timedelta(days=14),
        )


@pytest.mark.django_db
def test_clean_prevents_duplicate_course_level_deadline(
    mock_site_context, cohort_course_reg
):
    """clean() raises ValidationError for duplicate course-level deadlines."""
    from django.core.exceptions import ValidationError

    CohortDeadline.objects.create(
        cohort_course_registration=cohort_course_reg,
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    duplicate = CohortDeadline(
        cohort_course_registration=cohort_course_reg,
        deadline=timezone.now() + timezone.timedelta(days=14),
    )

    with pytest.raises(ValidationError):
        duplicate.clean()


@pytest.mark.django_db
def test_default_is_hard_deadline(mock_site_context, cohort_course_reg):
    """is_hard_deadline defaults to True."""
    deadline = CohortDeadline.objects.create(
        cohort_course_registration=cohort_course_reg,
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    assert deadline.is_hard_deadline is True
