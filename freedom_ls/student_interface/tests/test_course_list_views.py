"""Tests for all_courses and partial_list_courses views."""

import pytest

from django.test import Client
from django.urls import reverse
from django.utils import timezone

from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.student_management.factories import (
    RecommendedCourseFactory,
    StudentCourseRegistrationFactory,
    StudentFactory,
)
from freedom_ls.student_progress.factories import CourseProgressFactory


@pytest.fixture
def courses(mock_site_context) -> list[Course]:
    """Create three courses, each with a topic so progress can be calculated."""
    result = []
    for i, title in enumerate(["Course A", "Course B", "Course C"]):
        slug = title.lower().replace(" ", "-")
        course = CourseFactory(title=title, slug=slug)
        topic = TopicFactory(title=f"Topic {i}", slug=f"topic-{i}", content="content")
        course.items.create(child=topic, order=0)
        result.append(course)
    return result


# --- all_courses view ---


@pytest.mark.django_db
def test_all_courses_started_course_has_progress_percentage(
    mock_site_context, courses
):
    """Started courses in the all_courses view should have progress_percentage for progress bars."""
    student = StudentFactory()
    StudentCourseRegistrationFactory(student=student, collection=courses[0])
    client = Client()
    client.force_login(student.user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    all_courses_list = list(response.context["all_courses"])
    started_course = next(c for c in all_courses_list if c.id == courses[0].id)
    assert hasattr(started_course, "progress_percentage")


# --- partial_list_courses view ---


@pytest.mark.django_db
def test_partial_list_courses_anonymous_sees_empty(client, courses, mock_site_context):
    """Anonymous user sees empty course lists."""
    response = client.get(reverse("student_interface:partial_list_courses"))
    assert response.status_code == 200
    assert response.context["registered_courses"] == []
    assert response.context["completed_courses"] == []


@pytest.mark.django_db
def test_partial_list_courses_current_courses(mock_site_context, courses):
    """Registered non-completed courses show up as registered_courses."""
    student = StudentFactory()
    StudentCourseRegistrationFactory(student=student, collection=courses[0])
    client = Client()
    client.force_login(student.user)

    response = client.get(reverse("student_interface:partial_list_courses"))
    assert response.status_code == 200
    registered = response.context["registered_courses"]
    assert len(registered) == 1
    assert registered[0] == courses[0]


@pytest.mark.django_db
def test_partial_list_courses_current_courses_have_progress_percentage(
    mock_site_context, courses
):
    """Current courses should have progress_percentage attribute for progress bars."""
    student = StudentFactory()
    StudentCourseRegistrationFactory(student=student, collection=courses[0])
    client = Client()
    client.force_login(student.user)

    response = client.get(reverse("student_interface:partial_list_courses"))
    registered = response.context["registered_courses"]
    assert len(registered) == 1
    assert hasattr(registered[0], "progress_percentage")


@pytest.mark.django_db
def test_partial_list_courses_completed_courses(mock_site_context, courses):
    """Completed courses show up in completed_courses, not registered_courses."""
    student = StudentFactory()
    StudentCourseRegistrationFactory(student=student, collection=courses[0])
    CourseProgressFactory(
        user=student.user, course=courses[0], completed_time=timezone.now()
    )
    client = Client()
    client.force_login(student.user)

    response = client.get(reverse("student_interface:partial_list_courses"))
    assert response.status_code == 200
    assert courses[0] in response.context["completed_courses"]
    assert courses[0] not in list(response.context["registered_courses"])


@pytest.mark.django_db
def test_partial_list_courses_includes_recommended_courses(
    mock_site_context, courses
):
    """Recommended courses are passed to the template context."""
    student = StudentFactory()
    RecommendedCourseFactory(user=student.user, collection=courses[0])
    client = Client()
    client.force_login(student.user)

    response = client.get(reverse("student_interface:partial_list_courses"))
    assert response.status_code == 200
    recommended = list(response.context["recommended_courses"])
    assert len(recommended) == 1
    assert recommended[0].collection == courses[0]
