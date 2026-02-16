"""Tests for course_student_progress view."""

import pytest
from django.test import Client
from django.urls import reverse
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from freedom_ls.content_engine.models import (
    Course,
    CoursePart,
    Topic,
    Form,
    ContentCollectionItem,
)
from freedom_ls.student_management.models import (
    Student,
    Cohort,
    CohortMembership,
    StudentCourseRegistration,
    CohortCourseRegistration,
)
from freedom_ls.student_progress.models import TopicProgress, FormProgress


def _add_child_to_course(parent, child):
    """Helper to add a content item as a child of a course or course part."""
    parent_ct = ContentType.objects.get_for_model(parent)
    child_ct = ContentType.objects.get_for_model(child)
    return ContentCollectionItem.objects.create(
        collection_type=parent_ct,
        collection_id=parent.pk,
        child_type=child_ct,
        child_id=child.pk,
        order=ContentCollectionItem.objects.filter(
            collection_type=parent_ct, collection_id=parent.pk
        ).count(),
    )


def _create_student(user_cls, email, first_name, last_name):
    """Helper to create a user and student."""
    u = user_cls.objects.create_user(email=email, password="testpass123")
    u.first_name = first_name
    u.last_name = last_name
    u.save()
    return Student.objects.create(user=u), u


def _get_progress_url(course_slug):
    return reverse(
        "educator_interface:course_student_progress",
        kwargs={"course_slug": course_slug},
    )


@pytest.mark.django_db
def test_view_returns_course_items_in_context(mock_site_context, user):
    """View context includes flattened course items (topics/forms, not CourseParts)."""
    course = Course.objects.create(title="Test Course", slug="test-course")
    topic1 = Topic.objects.create(title="Topic 1", slug="topic-1")
    topic2 = Topic.objects.create(title="Topic 2", slug="topic-2")
    _add_child_to_course(course, topic1)
    _add_child_to_course(course, topic2)

    client = Client()
    client.force_login(user)
    response = client.get(_get_progress_url("test-course"))

    assert response.status_code == 200
    course_items = response.context["course_items"]
    assert len(course_items) == 2
    assert course_items[0].title == "Topic 1"
    assert course_items[1].title == "Topic 2"


@pytest.mark.django_db
def test_view_returns_students_registered_for_course(mock_site_context, user):
    """View context includes students from both direct and cohort registrations."""
    course = Course.objects.create(title="Test Course", slug="test-course")

    # Direct registration
    student1, _ = _create_student(user.__class__, "alice@example.com", "Alice", "Smith")
    StudentCourseRegistration.objects.create(collection=course, student=student1)

    # Cohort registration
    student2, _ = _create_student(user.__class__, "bob@example.com", "Bob", "Jones")
    cohort = Cohort.objects.create(name="Cohort A")
    CohortMembership.objects.create(student=student2, cohort=cohort)
    CohortCourseRegistration.objects.create(collection=course, cohort=cohort)

    client = Client()
    client.force_login(user)
    response = client.get(_get_progress_url("test-course"))

    assert response.status_code == 200
    students = response.context["students"]
    assert len(students) == 2
    student_names = {str(s) for s in students}
    assert "Alice Smith" in student_names
    assert "Bob Jones" in student_names


@pytest.mark.django_db
def test_progress_data_for_completed_topic(mock_site_context, user):
    """Progress data for a completed topic includes status and completed_date."""
    course = Course.objects.create(title="Test Course", slug="test-course")
    topic = Topic.objects.create(title="Topic 1", slug="topic-1")
    _add_child_to_course(course, topic)

    student, student_user = _create_student(
        user.__class__, "alice@example.com", "Alice", "Smith"
    )
    StudentCourseRegistration.objects.create(collection=course, student=student)

    completed_at = timezone.now()
    TopicProgress.objects.create(
        user=student_user, topic=topic, complete_time=completed_at
    )

    client = Client()
    client.force_login(user)
    response = client.get(_get_progress_url("test-course"))

    progress = response.context["students"][0].progress[str(topic.pk)]
    assert progress["status"] == "completed"
    assert progress["completed_date"] == completed_at
    assert progress["item_type"] == "TOPIC"


@pytest.mark.django_db
def test_progress_data_for_in_progress_topic(mock_site_context, user):
    """Progress data for an in-progress topic (started but not completed)."""
    course = Course.objects.create(title="Test Course", slug="test-course")
    topic = Topic.objects.create(title="Topic 1", slug="topic-1")
    _add_child_to_course(course, topic)

    student, student_user = _create_student(
        user.__class__, "alice@example.com", "Alice", "Smith"
    )
    StudentCourseRegistration.objects.create(collection=course, student=student)

    # Started but not completed
    TopicProgress.objects.create(user=student_user, topic=topic)

    client = Client()
    client.force_login(user)
    response = client.get(_get_progress_url("test-course"))

    progress = response.context["students"][0].progress[str(topic.pk)]
    assert progress["status"] == "in_progress"
    assert progress["completed_date"] is None


@pytest.mark.django_db
def test_progress_data_for_not_started_topic(mock_site_context, user):
    """Progress data for a topic with no progress record."""
    course = Course.objects.create(title="Test Course", slug="test-course")
    topic = Topic.objects.create(title="Topic 1", slug="topic-1")
    _add_child_to_course(course, topic)

    student, _ = _create_student(
        user.__class__, "alice@example.com", "Alice", "Smith"
    )
    StudentCourseRegistration.objects.create(collection=course, student=student)

    client = Client()
    client.force_login(user)
    response = client.get(_get_progress_url("test-course"))

    progress = response.context["students"][0].progress[str(topic.pk)]
    assert progress["status"] == "not_started"


@pytest.mark.django_db
def test_progress_data_for_completed_quiz(mock_site_context, user):
    """Progress data for a completed quiz includes attempt count and latest score."""
    course = Course.objects.create(title="Test Course", slug="test-course")
    form = Form.objects.create(
        title="Quiz 1", slug="quiz-1", strategy="QUIZ",
        quiz_pass_percentage=50, quiz_show_incorrect=True,
    )
    _add_child_to_course(course, form)

    student, student_user = _create_student(
        user.__class__, "alice@example.com", "Alice", "Smith"
    )
    StudentCourseRegistration.objects.create(collection=course, student=student)

    # Two completed attempts with scores
    FormProgress.objects.create(
        user=student_user, form=form,
        completed_time=timezone.now(),
        scores={"score": 1, "max_score": 2},
    )
    FormProgress.objects.create(
        user=student_user, form=form,
        completed_time=timezone.now(),
        scores={"score": 2, "max_score": 2},
    )

    client = Client()
    client.force_login(user)
    response = client.get(_get_progress_url("test-course"))

    progress = response.context["students"][0].progress[str(form.pk)]
    assert progress["status"] == "completed"
    assert progress["is_quiz"] is True
    assert progress["attempt_count"] == 2
    assert progress["latest_score"] == 100  # 2/2 * 100


@pytest.mark.django_db
def test_progress_data_for_in_progress_form(mock_site_context, user):
    """Progress data for a form that has been started but not completed."""
    course = Course.objects.create(title="Test Course", slug="test-course")
    form = Form.objects.create(
        title="Quiz 1", slug="quiz-1", strategy="QUIZ",
        quiz_pass_percentage=50, quiz_show_incorrect=True,
    )
    _add_child_to_course(course, form)

    student, student_user = _create_student(
        user.__class__, "alice@example.com", "Alice", "Smith"
    )
    StudentCourseRegistration.objects.create(collection=course, student=student)

    # Started but not completed
    FormProgress.objects.create(user=student_user, form=form)

    client = Client()
    client.force_login(user)
    response = client.get(_get_progress_url("test-course"))

    progress = response.context["students"][0].progress[str(form.pk)]
    assert progress["status"] == "in_progress"
    assert progress["is_quiz"] is True
    assert progress["attempt_count"] == 1
    assert progress["latest_score"] is None


@pytest.mark.django_db
def test_course_items_excludes_course_parts(mock_site_context, user):
    """CoursePart items are excluded from course_items; their children are included."""
    course = Course.objects.create(title="Test Course", slug="test-course")
    part = CoursePart.objects.create(title="Chapter 1", slug="chapter-1")
    topic = Topic.objects.create(title="Topic in Part", slug="topic-in-part")

    _add_child_to_course(course, part)
    _add_child_to_course(part, topic)

    client = Client()
    client.force_login(user)
    response = client.get(_get_progress_url("test-course"))

    course_items = response.context["course_items"]
    item_titles = [item.title for item in course_items]
    assert "Chapter 1" not in item_titles
    assert "Topic in Part" in item_titles


@pytest.mark.django_db
def test_template_renders_student_rows_and_item_columns(mock_site_context, user):
    """Template renders a table with student rows and course item columns."""
    course = Course.objects.create(title="Test Course", slug="test-course")
    topic = Topic.objects.create(title="Topic 1", slug="topic-1")
    form = Form.objects.create(title="Form 1", slug="form-1", strategy="QUIZ")
    _add_child_to_course(course, topic)
    _add_child_to_course(course, form)

    student, student_user = _create_student(
        user.__class__, "alice@example.com", "Alice", "Smith"
    )
    StudentCourseRegistration.objects.create(collection=course, student=student)

    TopicProgress.objects.create(
        user=student_user, topic=topic, complete_time=timezone.now()
    )

    client = Client()
    client.force_login(user)
    response = client.get(_get_progress_url("test-course"))
    content = response.content.decode()

    # Table headers should include item titles
    assert "Topic 1" in content
    assert "Form 1" in content
    # Student name should appear
    assert "Alice Smith" in content


@pytest.mark.django_db
def test_empty_message_when_no_students(mock_site_context, user):
    """Shows empty message when no students are registered for the course."""
    Course.objects.create(title="Test Course", slug="test-course")

    client = Client()
    client.force_login(user)
    response = client.get(_get_progress_url("test-course"))
    content = response.content.decode()

    assert "No students are registered for this course." in content


@pytest.mark.django_db
def test_template_shows_quiz_score_and_attempt_count(mock_site_context, user):
    """Template renders quiz score and attempt count for completed quizzes."""
    course = Course.objects.create(title="Test Course", slug="test-course")
    form = Form.objects.create(
        title="Quiz 1", slug="quiz-1", strategy="QUIZ",
        quiz_pass_percentage=50, quiz_show_incorrect=True,
    )
    _add_child_to_course(course, form)

    student, student_user = _create_student(
        user.__class__, "alice@example.com", "Alice", "Smith"
    )
    StudentCourseRegistration.objects.create(collection=course, student=student)

    FormProgress.objects.create(
        user=student_user, form=form,
        completed_time=timezone.now(),
        scores={"score": 3, "max_score": 4},
    )

    client = Client()
    client.force_login(user)
    response = client.get(_get_progress_url("test-course"))
    content = response.content.decode()

    assert "75%" in content
    assert "1 attempt" in content


@pytest.mark.django_db
def test_template_shows_in_progress_indicator(mock_site_context, user):
    """Template shows in-progress indicator for started but incomplete items."""
    course = Course.objects.create(title="Test Course", slug="test-course")
    topic = Topic.objects.create(title="Topic 1", slug="topic-1")
    _add_child_to_course(course, topic)

    student, student_user = _create_student(
        user.__class__, "alice@example.com", "Alice", "Smith"
    )
    StudentCourseRegistration.objects.create(collection=course, student=student)

    # Started but not completed
    TopicProgress.objects.create(user=student_user, topic=topic)

    client = Client()
    client.force_login(user)
    response = client.get(_get_progress_url("test-course"))
    content = response.content.decode()

    assert "In progress" in content
