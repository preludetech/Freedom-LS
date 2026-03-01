from datetime import timedelta

import pytest

from django.utils import timezone

from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.student_management.factories import (
    CohortCourseRegistrationFactory,
    CohortDeadlineFactory,
    CohortFactory,
)
from freedom_ls.student_management.models import CohortDeadline


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
def test_str_with_content_item(mock_site_context):
    """__str__ includes the content item name."""
    topic = TopicFactory(title="Test Topic")
    cohort = CohortFactory(name="Test Cohort")
    course = CourseFactory(title="Test Course")
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    deadline = CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
        content_item=topic,
    )

    assert str(deadline) == "Test Cohort - Test Course - Test Topic"


@pytest.mark.django_db
def test_str_without_content_item(mock_site_context):
    """__str__ shows 'Whole course' when content_item is null."""
    cohort = CohortFactory(name="Test Cohort")
    course = CourseFactory(title="Test Course")
    cohort_course_reg = CohortCourseRegistrationFactory(cohort=cohort, collection=course)

    deadline = CohortDeadlineFactory(
        cohort_course_registration=cohort_course_reg,
    )

    assert str(deadline) == "Test Cohort - Test Course - Whole course"


@pytest.mark.django_db
def test_unique_constraint_prevents_duplicate_item_deadline(mock_site_context):
    """Cannot create two deadlines for the same content item on the same registration."""
    from django.db import IntegrityError

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
def test_clean_prevents_duplicate_course_level_deadline(mock_site_context):
    """clean() raises ValidationError for duplicate course-level deadlines."""
    from django.core.exceptions import ValidationError

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
def test_default_is_hard_deadline(mock_site_context):
    """is_hard_deadline defaults to True."""
    cohort_course_reg = CohortCourseRegistrationFactory()

    deadline = CohortDeadline.objects.create(
        cohort_course_registration=cohort_course_reg,
        deadline=timezone.now() + timedelta(days=7),
    )

    assert deadline.is_hard_deadline is True
