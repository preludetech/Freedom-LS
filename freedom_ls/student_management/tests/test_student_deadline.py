import pytest
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from freedom_ls.content_engine.models import Course, Topic
from freedom_ls.student_management.models import (
    Student,
    StudentCourseRegistration,
    StudentDeadline,
)


@pytest.fixture
def course(mock_site_context):
    """Create a test course."""
    return Course.objects.create(title="Test Course", slug="test-course")


@pytest.fixture
def topic(mock_site_context):
    """Create a test topic."""
    return Topic.objects.create(title="Test Topic", slug="test-topic")


@pytest.fixture
def student(mock_site_context, user):
    """Create a test student."""
    return Student.objects.create(user=user)


@pytest.fixture
def student_course_reg(mock_site_context, student, course):
    """Create a student course registration."""
    return StudentCourseRegistration.objects.create(
        student=student, collection=course
    )


@pytest.mark.django_db
def test_create_student_deadline_with_content_item(
    mock_site_context, student_course_reg, topic
):
    """StudentDeadline can be created pointing to a specific content item."""
    topic_ct = ContentType.objects.get_for_model(Topic)
    deadline_dt = timezone.now() + timezone.timedelta(days=7)

    deadline = StudentDeadline.objects.create(
        student_course_registration=student_course_reg,
        content_type=topic_ct,
        object_id=topic.id,
        deadline=deadline_dt,
    )

    assert deadline.student_course_registration == student_course_reg
    assert deadline.content_item == topic
    assert deadline.is_hard_deadline is True


@pytest.mark.django_db
def test_create_student_deadline_for_whole_course(
    mock_site_context, student_course_reg
):
    """StudentDeadline with null content_item applies to the whole course."""
    deadline = StudentDeadline.objects.create(
        student_course_registration=student_course_reg,
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    assert deadline.content_item is None


@pytest.mark.django_db
def test_str_with_content_item(mock_site_context, student_course_reg, topic):
    """__str__ includes the content item name."""
    topic_ct = ContentType.objects.get_for_model(Topic)
    deadline = StudentDeadline.objects.create(
        student_course_registration=student_course_reg,
        content_type=topic_ct,
        object_id=topic.id,
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    assert "Test Topic" in str(deadline)


@pytest.mark.django_db
def test_str_without_content_item(mock_site_context, student_course_reg):
    """__str__ shows 'Whole course' when content_item is null."""
    deadline = StudentDeadline.objects.create(
        student_course_registration=student_course_reg,
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    assert "Whole course" in str(deadline)


@pytest.mark.django_db
def test_unique_constraint_prevents_duplicate_item_deadline(
    mock_site_context, student_course_reg, topic
):
    """Cannot create two deadlines for the same content item on the same registration."""
    topic_ct = ContentType.objects.get_for_model(Topic)
    StudentDeadline.objects.create(
        student_course_registration=student_course_reg,
        content_type=topic_ct,
        object_id=topic.id,
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    with pytest.raises(IntegrityError):
        StudentDeadline.objects.create(
            student_course_registration=student_course_reg,
            content_type=topic_ct,
            object_id=topic.id,
            deadline=timezone.now() + timezone.timedelta(days=14),
        )


@pytest.mark.django_db
def test_clean_prevents_duplicate_course_level_deadline(
    mock_site_context, student_course_reg
):
    """clean() raises ValidationError for duplicate course-level deadlines."""
    StudentDeadline.objects.create(
        student_course_registration=student_course_reg,
        deadline=timezone.now() + timezone.timedelta(days=7),
    )

    duplicate = StudentDeadline(
        student_course_registration=student_course_reg,
        deadline=timezone.now() + timezone.timedelta(days=14),
    )

    with pytest.raises(ValidationError):
        duplicate.clean()
