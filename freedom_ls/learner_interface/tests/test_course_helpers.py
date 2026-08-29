"""Tests for course helper functions in learner_interface.utils."""

import pytest

from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.learner_interface.utils import (
    get_all_courses,
    get_completed_courses,
    get_current_courses,
)
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory

from .conftest import course_progress_record

# --- get_all_courses ---


@pytest.mark.django_db
def test_get_all_courses_returns_all(mock_site_context):
    """get_all_courses returns all courses regardless of user."""
    courses = CourseFactory.create_batch(3)
    result = get_all_courses()
    # get_all_courses carries no ordering contract, so compare membership
    # rather than row order.
    assert set(result) == set(courses)


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
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    result = get_completed_courses(user)
    assert result == []


@pytest.mark.django_db
def test_get_completed_courses_returns_completed(mock_site_context):
    """get_completed_courses returns only completed courses."""
    user = UserFactory()
    course_a = CourseFactory()
    course_b = CourseFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course_a)
    LearnerCourseRegistrationFactory(learner__user=user, course=course_b)

    # Complete course_a only
    course_progress_record(course_a, user, completed_time=timezone.now())

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
    LearnerCourseRegistrationFactory(learner__user=user, course=course)

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
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    course_progress_record(course, user, completed_time=timezone.now())

    result = get_current_courses(user)
    assert result == []


@pytest.mark.django_db
def test_get_current_courses_have_progress_percentage(mock_site_context):
    """get_current_courses attaches progress_percentage to each course."""
    user = UserFactory()
    course: Course = CourseFactory()
    topic = TopicFactory(content="content")
    course.items.create(child=topic, order=0)
    LearnerCourseRegistrationFactory(learner__user=user, course=course)

    result = get_current_courses(user)
    assert len(result) == 1
    assert result[0].progress_percentage == 0
