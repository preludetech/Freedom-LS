"""Tests for course helper functions in student_interface.utils."""

import pytest

from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.student_interface.utils import (
    get_all_courses,
    get_completed_courses,
    get_current_courses,
    get_recommended_courses,
)
from freedom_ls.student_management.factories import (
    RecommendedCourseFactory,
    UserCourseRegistrationFactory,
)
from freedom_ls.student_progress.factories import CourseProgressFactory

# --- get_all_courses ---


@pytest.mark.django_db
def test_get_all_courses_returns_all(mock_site_context):
    """get_all_courses returns all courses regardless of user."""
    courses = CourseFactory.create_batch(3)
    result = get_all_courses()
    assert list(result) == courses


@pytest.mark.django_db
def test_get_all_courses_returns_empty_when_none_exist(mock_site_context):
    """get_all_courses returns empty queryset when no courses exist."""
    result = get_all_courses()
    assert list(result) == []


# --- get_completed_courses ---


@pytest.mark.django_db
def test_get_completed_courses_anonymous_user(mock_site_context):
    """get_completed_courses returns empty list for anonymous user."""
    CourseFactory.create_batch(2)
    result = get_completed_courses(AnonymousUser())
    assert result == []


@pytest.mark.django_db
def test_get_completed_courses_user_without_registrations(mock_site_context):
    """get_completed_courses returns empty list for user without registrations."""
    CourseFactory.create_batch(2)
    user = UserFactory()
    result = get_completed_courses(user)
    assert result == []


@pytest.mark.django_db
def test_get_completed_courses_no_completed(mock_site_context):
    """get_completed_courses returns empty list when no courses are completed."""
    user = UserFactory()
    course = CourseFactory()
    UserCourseRegistrationFactory(user=user, collection=course)
    result = get_completed_courses(user)
    assert result == []


@pytest.mark.django_db
def test_get_completed_courses_returns_completed(mock_site_context):
    """get_completed_courses returns only completed courses."""
    user = UserFactory()
    course_a = CourseFactory()
    course_b = CourseFactory()
    UserCourseRegistrationFactory(user=user, collection=course_a)
    UserCourseRegistrationFactory(user=user, collection=course_b)

    # Complete course_a only
    CourseProgressFactory(user=user, course=course_a, completed_time=timezone.now())

    result = get_completed_courses(user)
    assert result == [course_a]


# --- get_current_courses ---


@pytest.mark.django_db
def test_get_current_courses_anonymous_user(mock_site_context):
    """get_current_courses returns empty list for anonymous user."""
    CourseFactory.create_batch(2)
    result = get_current_courses(AnonymousUser())
    assert result == []


@pytest.mark.django_db
def test_get_current_courses_user_without_registrations(mock_site_context):
    """get_current_courses returns empty list for user without registrations."""
    CourseFactory.create_batch(2)
    user = UserFactory()
    result = get_current_courses(user)
    assert result == []


@pytest.mark.django_db
def test_get_current_courses_returns_non_completed_registered(mock_site_context):
    """get_current_courses returns registered courses that are not completed."""
    user = UserFactory()
    course: Course = CourseFactory()
    topic = TopicFactory(content="content")
    course.items.create(child=topic, order=0)
    UserCourseRegistrationFactory(user=user, collection=course)

    result = get_current_courses(user)
    assert len(result) == 1
    assert result[0] == course


@pytest.mark.django_db
def test_get_current_courses_excludes_completed(mock_site_context):
    """get_current_courses excludes courses that are completed."""
    user = UserFactory()
    course: Course = CourseFactory()
    topic = TopicFactory(content="content")
    course.items.create(child=topic, order=0)
    UserCourseRegistrationFactory(user=user, collection=course)
    CourseProgressFactory(user=user, course=course, completed_time=timezone.now())

    result = get_current_courses(user)
    assert result == []


@pytest.mark.django_db
def test_get_current_courses_have_progress_percentage(mock_site_context):
    """get_current_courses attaches progress_percentage to each course."""
    user = UserFactory()
    course: Course = CourseFactory()
    topic = TopicFactory(content="content")
    course.items.create(child=topic, order=0)
    UserCourseRegistrationFactory(user=user, collection=course)

    result = get_current_courses(user)
    assert len(result) == 1
    assert hasattr(result[0], "progress_percentage")


# --- get_recommended_courses ---


@pytest.mark.django_db
def test_get_recommended_courses_anonymous_user(mock_site_context):
    """get_recommended_courses returns empty queryset for anonymous user."""
    result = get_recommended_courses(AnonymousUser())
    assert list(result) == []


@pytest.mark.django_db
def test_get_recommended_courses_none_exist(mock_site_context):
    """get_recommended_courses returns empty queryset when none exist."""
    user = UserFactory()
    result = get_recommended_courses(user)
    assert list(result) == []


@pytest.mark.django_db
def test_get_recommended_courses_returns_recommendations(mock_site_context):
    """get_recommended_courses returns recommendations for the user."""
    user = UserFactory()
    courses = CourseFactory.create_batch(2)
    RecommendedCourseFactory(user=user, collection=courses[0])
    RecommendedCourseFactory(user=user, collection=courses[1])

    result = get_recommended_courses(user)
    assert len(result) == 2
    collections = [r.collection for r in result]
    assert courses[0] in collections
    assert courses[1] in collections


@pytest.mark.django_db
def test_get_recommended_courses_only_for_given_user(mock_site_context):
    """get_recommended_courses only returns recommendations for the given user."""
    user = UserFactory()
    other_user = UserFactory()
    courses = CourseFactory.create_batch(2)
    RecommendedCourseFactory(user=user, collection=courses[0])
    RecommendedCourseFactory(user=other_user, collection=courses[1])

    result = get_recommended_courses(user)
    assert len(result) == 1
    assert result[0].collection == courses[0]
