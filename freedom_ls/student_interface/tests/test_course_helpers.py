"""Tests for course helper functions in student_interface.utils."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from freedom_ls.content_engine.models import Course, Topic
from freedom_ls.student_management.models import (
    Student,
    StudentCourseRegistration,
    RecommendedCourse,
)
from freedom_ls.student_progress.models import CourseProgress, TopicProgress
from django.utils import timezone

from freedom_ls.student_interface.utils import (
    get_all_courses,
    get_completed_courses,
    get_current_courses,
    get_recommended_courses,
)

User = get_user_model()


@pytest.fixture
def anonymous_user():
    """Create an anonymous user."""
    return AnonymousUser()


@pytest.fixture
def authenticated_user(mock_site_context):
    """Create an authenticated user without a student profile."""
    return User.objects.create_user(email="notstudent@example.com", password="pass")


@pytest.fixture
def student_user(mock_site_context):
    """Create an authenticated user with a student profile."""
    user = User.objects.create_user(email="student@example.com", password="pass")
    Student.objects.create(user=user)
    return user


@pytest.fixture
def courses(mock_site_context) -> list[Course]:
    """Create three test courses."""
    return [
        Course.objects.create(title="Course A", slug="course-a"),
        Course.objects.create(title="Course B", slug="course-b"),
        Course.objects.create(title="Course C", slug="course-c"),
    ]


@pytest.fixture
def course_with_topic(mock_site_context) -> Course:
    """Create a course with a single topic."""
    course = Course.objects.create(title="Topic Course", slug="topic-course")
    topic = Topic.objects.create(title="Topic 1", slug="topic-1", content="content")
    course.items.create(child=topic, order=0)
    return course


# --- get_all_courses ---


@pytest.mark.django_db
def test_get_all_courses_returns_all(courses):
    """get_all_courses returns all courses regardless of user."""
    result = get_all_courses()
    assert list(result) == courses


@pytest.mark.django_db
def test_get_all_courses_returns_empty_when_none_exist(mock_site_context):
    """get_all_courses returns empty queryset when no courses exist."""
    result = get_all_courses()
    assert list(result) == []


# --- get_completed_courses ---


@pytest.mark.django_db
def test_get_completed_courses_anonymous_user(anonymous_user, courses):
    """get_completed_courses returns empty list for anonymous user."""
    result = get_completed_courses(anonymous_user)
    assert result == []


@pytest.mark.django_db
def test_get_completed_courses_user_without_student(authenticated_user, courses):
    """get_completed_courses returns empty list for user without student profile."""
    result = get_completed_courses(authenticated_user)
    assert result == []


@pytest.mark.django_db
def test_get_completed_courses_no_completed(student_user, courses):
    """get_completed_courses returns empty list when no courses are completed."""
    student = Student.objects.get(user=student_user)
    StudentCourseRegistration.objects.create(student=student, collection=courses[0])
    result = get_completed_courses(student_user)
    assert result == []


@pytest.mark.django_db
def test_get_completed_courses_returns_completed(student_user, courses):
    """get_completed_courses returns only completed courses."""
    student = Student.objects.get(user=student_user)
    StudentCourseRegistration.objects.create(student=student, collection=courses[0])
    StudentCourseRegistration.objects.create(student=student, collection=courses[1])

    # Complete course 0 only
    CourseProgress.objects.create(
        user=student_user, course=courses[0], completed_time=timezone.now()
    )

    result = get_completed_courses(student_user)
    assert result == [courses[0]]


# --- get_current_courses ---


@pytest.mark.django_db
def test_get_current_courses_anonymous_user(anonymous_user, courses):
    """get_current_courses returns empty list for anonymous user."""
    result = get_current_courses(anonymous_user)
    assert result == []


@pytest.mark.django_db
def test_get_current_courses_user_without_student(authenticated_user, courses):
    """get_current_courses returns empty list for user without student profile."""
    result = get_current_courses(authenticated_user)
    assert result == []


@pytest.mark.django_db
def test_get_current_courses_returns_non_completed_registered(
    student_user, course_with_topic
):
    """get_current_courses returns registered courses that are not completed."""
    student = Student.objects.get(user=student_user)
    StudentCourseRegistration.objects.create(
        student=student, collection=course_with_topic
    )

    result = get_current_courses(student_user)
    assert len(result) == 1
    assert result[0] == course_with_topic


@pytest.mark.django_db
def test_get_current_courses_excludes_completed(student_user, course_with_topic):
    """get_current_courses excludes courses that are completed."""
    student = Student.objects.get(user=student_user)
    StudentCourseRegistration.objects.create(
        student=student, collection=course_with_topic
    )
    CourseProgress.objects.create(
        user=student_user, course=course_with_topic, completed_time=timezone.now()
    )

    result = get_current_courses(student_user)
    assert result == []


@pytest.mark.django_db
def test_get_current_courses_have_progress_percentage(
    student_user, course_with_topic
):
    """get_current_courses attaches progress_percentage to each course."""
    student = Student.objects.get(user=student_user)
    StudentCourseRegistration.objects.create(
        student=student, collection=course_with_topic
    )

    result = get_current_courses(student_user)
    assert len(result) == 1
    assert hasattr(result[0], "progress_percentage")


# --- get_recommended_courses ---


@pytest.mark.django_db
def test_get_recommended_courses_anonymous_user(anonymous_user):
    """get_recommended_courses returns empty queryset for anonymous user."""
    result = get_recommended_courses(anonymous_user)
    assert list(result) == []


@pytest.mark.django_db
def test_get_recommended_courses_none_exist(student_user):
    """get_recommended_courses returns empty queryset when none exist."""
    result = get_recommended_courses(student_user)
    assert list(result) == []


@pytest.mark.django_db
def test_get_recommended_courses_returns_recommendations(student_user, courses):
    """get_recommended_courses returns recommendations for the user."""
    RecommendedCourse.objects.create(user=student_user, collection=courses[0])
    RecommendedCourse.objects.create(user=student_user, collection=courses[1])

    result = get_recommended_courses(student_user)
    assert len(result) == 2
    collections = [r.collection for r in result]
    assert courses[0] in collections
    assert courses[1] in collections


@pytest.mark.django_db
def test_get_recommended_courses_only_for_given_user(student_user, courses, mock_site_context):
    """get_recommended_courses only returns recommendations for the given user."""
    other_user = User.objects.create_user(email="other@example.com", password="pass")
    RecommendedCourse.objects.create(user=student_user, collection=courses[0])
    RecommendedCourse.objects.create(user=other_user, collection=courses[1])

    result = get_recommended_courses(student_user)
    assert len(result) == 1
    assert result[0].collection == courses[0]
