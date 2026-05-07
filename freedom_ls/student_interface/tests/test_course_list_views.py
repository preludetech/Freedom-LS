"""Tests for the all_courses view and the dashboard view.

The dashboard view replaces the old ``partial_list_courses`` HTMX
endpoint; tests for that endpoint were deleted in the same change set.
"""

from __future__ import annotations

import pytest

from django.test import Client
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.student_management.factories import (
    RecommendedCourseFactory,
    UserCourseRegistrationFactory,
)
from freedom_ls.student_progress.factories import CourseProgressFactory


@pytest.fixture
def courses(mock_site_context) -> list[Course]:
    """Create three courses, each with a topic so progress can be calculated."""
    result = []
    for i, title in enumerate(["Course A", "Course B", "Course C"]):
        slug = title.lower().replace(" ", "-")
        course: Course = CourseFactory(title=title, slug=slug)
        topic = TopicFactory(title=f"Topic {i}", slug=f"topic-{i}", content="content")
        course.items.create(child=topic, order=0)
        result.append(course)
    return result


def _logged_in_client(user) -> Client:
    """Build a Client logged in as `user`. Local helper — do not lift across files."""
    client = Client()
    client.force_login(user)
    return client


# --- all_courses view ---


@pytest.mark.django_db
def test_all_courses_started_course_has_progress_percentage(mock_site_context, courses):
    """Started courses in the all_courses view should have progress_percentage for progress bars."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    all_courses_list = list(response.context["all_courses"])
    started_course = next(c for c in all_courses_list if c.id == courses[0].id)
    # Real-value assertion: a freshly-registered course with no topic
    # completion has a progress percentage of 0. `hasattr` only proved the
    # attribute existed; this proves the annotation produced the right value.
    assert started_course.progress_percentage == 0


@pytest.mark.django_db
def test_all_courses_annotates_accent_role(mock_site_context, courses):
    """Every course returned to the all_courses page has an ``accent_role``."""
    user = UserFactory()
    client = _logged_in_client(user)
    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200
    for course in response.context["all_courses"]:
        assert hasattr(course, "accent_role")
        assert course.accent_role in {
            "primary",
            "secondary",
            "accent",
            "info",
            "success",
        }


# --- dashboard view ---


@pytest.mark.django_db
def test_dashboard_anonymous_redirects_to_login(client, courses, mock_site_context):
    """Anonymous user hitting / is redirected to login (login_required)."""
    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 302
    # Login URL is the redirect target; we don't pin its exact path.
    assert "login" in response["Location"].lower()


@pytest.mark.django_db
def test_dashboard_authenticated_returns_200_with_user_label(
    mock_site_context, courses
):
    user = UserFactory()
    client = _logged_in_client(user)
    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    body = response.content.decode()
    # The greeting renders the user's first name (or email fallback).
    expected: str = user.first_name or user.email
    assert expected in body


@pytest.mark.django_db
def test_dashboard_current_courses(mock_site_context, courses):
    """Registered non-completed courses appear under registered_courses."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    registered = response.context["registered_courses"]
    assert len(registered) == 1
    assert registered[0] == courses[0]
    assert courses[0].title in response.content.decode()


@pytest.mark.django_db
def test_dashboard_current_courses_have_progress_percentage(mock_site_context, courses):
    """In-progress courses show progress_percentage attribute for progress bars."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    registered = response.context["registered_courses"]
    assert len(registered) == 1
    assert hasattr(registered[0], "progress_percentage")


@pytest.mark.django_db
def test_dashboard_completed_courses(mock_site_context, courses):
    """Completed courses surface in completed_courses, not registered_courses."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    CourseProgressFactory(user=user, course=courses[0], completed_time=timezone.now())
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    assert courses[0] in response.context["completed_courses"]
    assert courses[0] not in list(response.context["registered_courses"])
    assert courses[0].title in response.content.decode()


@pytest.mark.django_db
def test_dashboard_recommended_courses(mock_site_context, courses):
    """Recommended courses appear in recommended_courses context list."""
    user = UserFactory()
    RecommendedCourseFactory(user=user, collection=courses[0])
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    recommended = list(response.context["recommended_courses"])
    assert len(recommended) == 1
    assert recommended[0].collection == courses[0]
    assert courses[0].title in response.content.decode()


@pytest.mark.django_db
def test_dashboard_annotates_accent_on_every_course(mock_site_context, courses):
    """Every current/completed/recommended course gets an accent_role."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    UserCourseRegistrationFactory(user=user, collection=courses[1])
    CourseProgressFactory(user=user, course=courses[1], completed_time=timezone.now())
    RecommendedCourseFactory(user=user, collection=courses[2])
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200

    for course in response.context["registered_courses"]:
        assert hasattr(course, "accent_role")
    for course in response.context["completed_courses"]:
        assert hasattr(course, "accent_role")
    for rec in response.context["recommended_courses"]:
        assert hasattr(rec.collection, "accent_role")


# --- dead URL ---


@pytest.mark.django_db
def test_partial_list_courses_url_is_404(client, mock_site_context):
    """The old HTMX endpoint is gone; its path returns 404."""
    response = client.get("/partials/courses/")
    assert response.status_code == 404
