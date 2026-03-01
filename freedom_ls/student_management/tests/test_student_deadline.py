import pytest

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from freedom_ls.content_engine.factories import TopicFactory
from freedom_ls.student_management.factories import (
    StudentCourseRegistrationFactory,
    StudentDeadlineFactory,
)
from freedom_ls.student_management.models import StudentDeadline


@pytest.mark.django_db
def test_create_student_deadline_with_content_item(mock_site_context):
    """StudentDeadline can be created pointing to a specific content item."""
    topic = TopicFactory()
    student_course_reg = StudentCourseRegistrationFactory()

    deadline_dt = timezone.now() + timezone.timedelta(days=7)

    deadline: StudentDeadline = StudentDeadlineFactory(
        student_course_registration=student_course_reg,
        content_item=topic,
        deadline=deadline_dt,
        is_hard_deadline=True,
    )

    assert deadline.student_course_registration == student_course_reg
    assert deadline.content_item == topic
    assert deadline.is_hard_deadline is True


@pytest.mark.django_db
def test_create_student_deadline_for_whole_course(mock_site_context):
    """StudentDeadline with null content_item applies to the whole course."""
    student_course_reg = StudentCourseRegistrationFactory()

    deadline: StudentDeadline = StudentDeadlineFactory(
        student_course_registration=student_course_reg,
    )

    assert deadline.content_item is None


@pytest.mark.django_db
def test_str_with_content_item(mock_site_context):
    """__str__ includes the content item name."""
    topic = TopicFactory(title="Test Topic")
    student_course_reg = StudentCourseRegistrationFactory()

    deadline = StudentDeadlineFactory(
        student_course_registration=student_course_reg,
        content_item=topic,
    )

    assert "Test Topic" in str(deadline)


@pytest.mark.django_db
def test_str_without_content_item(mock_site_context):
    """__str__ shows 'Whole course' when content_item is null."""
    student_course_reg = StudentCourseRegistrationFactory()

    deadline = StudentDeadlineFactory(
        student_course_registration=student_course_reg,
    )

    assert "Whole course" in str(deadline)


@pytest.mark.django_db
def test_unique_constraint_prevents_duplicate_item_deadline(mock_site_context):
    """Cannot create two deadlines for the same content item on the same registration."""
    topic = TopicFactory()
    student_course_reg = StudentCourseRegistrationFactory()

    StudentDeadlineFactory(
        student_course_registration=student_course_reg,
        content_item=topic,
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    with pytest.raises(IntegrityError):
        StudentDeadlineFactory(
            student_course_registration=student_course_reg,
            content_item=topic,
            deadline=timezone.now() + timezone.timedelta(days=14),
        )


@pytest.mark.django_db
def test_clean_prevents_duplicate_course_level_deadline(mock_site_context):
    """clean() raises ValidationError for duplicate course-level deadlines."""
    student_course_reg = StudentCourseRegistrationFactory()

    StudentDeadlineFactory(
        student_course_registration=student_course_reg,
    )

    duplicate = StudentDeadline(
        student_course_registration=student_course_reg,
        deadline=timezone.now() + timezone.timedelta(days=14),
    )

    with pytest.raises(ValidationError):
        duplicate.clean()
