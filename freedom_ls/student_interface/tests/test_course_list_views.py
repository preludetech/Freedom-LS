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
def test_all_courses_anonymous_redirects_to_login(client, courses, mock_site_context):
    """Anonymous users get bounced to login — same gate as the dashboard."""
    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 302
    assert "login" in response["Location"].lower()


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
def test_all_courses_annotates_accent_slot_key(mock_site_context, courses):
    """Every course returned to the all_courses page has an ``accent_slot_key``."""
    user = UserFactory()
    client = _logged_in_client(user)
    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200
    from freedom_ls.content_engine.course_accent import PALETTE

    for course in response.context["all_courses"]:
        assert hasattr(course, "accent_slot_key")
        assert course.accent_slot_key in PALETTE


# --- dashboard view ---


@pytest.mark.django_db
def test_dashboard_authenticated_returns_200_with_user_label(
    mock_site_context, courses
):
    user = UserFactory(first_name="Ada")
    client = _logged_in_client(user)
    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    # The greeting renders the user's first name.
    assert "Ada" in response.content.decode()


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
    """Every current/completed/recommended course gets an accent_slot_key."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    UserCourseRegistrationFactory(user=user, collection=courses[1])
    CourseProgressFactory(user=user, course=courses[1], completed_time=timezone.now())
    RecommendedCourseFactory(user=user, collection=courses[2])
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200

    for course in response.context["registered_courses"]:
        assert hasattr(course, "accent_slot_key")
    for course in response.context["completed_courses"]:
        assert hasattr(course, "accent_slot_key")
    for rec in response.context["recommended_courses"]:
        assert hasattr(rec.collection, "accent_slot_key")


# --- dashboard available_courses ---


@pytest.mark.django_db
def test_dashboard_available_excludes_registered_and_completed(
    mock_site_context, courses
):
    """Available list omits both in-progress and completed registrations."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    UserCourseRegistrationFactory(user=user, collection=courses[1])
    CourseProgressFactory(user=user, course=courses[1], completed_time=timezone.now())
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    available = response.context["available_courses"]
    assert courses[0] not in available
    assert courses[1] not in available


@pytest.mark.django_db
def test_dashboard_available_excludes_recommended(mock_site_context, courses):
    """Recommended courses do not also appear in the available list."""
    user = UserFactory()
    RecommendedCourseFactory(user=user, collection=courses[0])
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    available = response.context["available_courses"]
    assert courses[0] not in available


@pytest.mark.django_db
def test_dashboard_available_capped_at_three(mock_site_context, courses):
    """No more than three available courses are surfaced, even with more eligible."""
    user = UserFactory()
    CourseFactory(title="Course D", slug="course-d")
    CourseFactory(title="Course E", slug="course-e")
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    assert len(response.context["available_courses"]) == 3


@pytest.mark.django_db
def test_dashboard_available_includes_eligible_course(mock_site_context, courses):
    """A course with no registration or recommendation shows up as available."""
    user = UserFactory()
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    available = response.context["available_courses"]
    assert courses[0] in available


@pytest.mark.django_db
def test_dashboard_available_courses_have_preview_annotations(
    mock_site_context, courses
):
    """Available courses carry preview context with is_registered False."""
    user = UserFactory()
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    available = response.context["available_courses"]
    assert available
    for course in available:
        assert course.preview_is_registered is False
        assert course.preview_start_url


# --- dashboard "Available courses" section + Browse-all link ---


@pytest.mark.django_db
def test_dashboard_available_section_renders_browse_all_link(
    mock_site_context, courses
):
    """When eligible courses exist, the section shows a Browse-all-courses link."""
    user = UserFactory()
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    body = response.content.decode()

    assert "Available courses" in body
    assert "Browse all courses" in body
    # A real anchor pointing at the all-courses page.
    courses_url = reverse("student_interface:courses")
    assert f'href="{courses_url}"' in body


@pytest.mark.django_db
def test_dashboard_available_section_hidden_when_empty(mock_site_context, courses):
    """With no eligible courses, the whole section (heading + link) disappears."""
    user = UserFactory()
    # Register two and recommend the third -> nothing left to surface.
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    UserCourseRegistrationFactory(user=user, collection=courses[1])
    RecommendedCourseFactory(user=user, collection=courses[2])
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    assert not response.context["available_courses"]
    body = response.content.decode()
    assert "Available courses" not in body
    assert "Browse all courses" not in body


@pytest.mark.django_db
def test_dashboard_old_all_courses_button_removed(mock_site_context, courses):
    """The old bottom 'All Courses' button no longer renders."""
    user = UserFactory()
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    assert "All Courses" not in response.content.decode()


@pytest.mark.django_db
def test_dashboard_empty_state_browse_courses_button_present(
    mock_site_context, courses
):
    """A learner with no registrations still sees the empty-state Browse button."""
    user = UserFactory()
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    body = response.content.decode()
    assert "You haven't signed up for any courses yet." in body
    assert "Browse courses" in body


@pytest.mark.django_db
def test_dashboard_completed_course_in_history_not_available(
    mock_site_context, courses
):
    """A completed course shows under Learning History, never under Available."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    CourseProgressFactory(user=user, course=courses[0], completed_time=timezone.now())
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    assert courses[0] in response.context["completed_courses"]
    assert courses[0] not in response.context["available_courses"]
    body = response.content.decode()
    assert "Learning History" in body


# --- page <title> tags (Bug 2) ---


def _extract_title(body: str) -> str:
    """Pull the trimmed text inside the first <title>...</title> tag."""
    start = body.find("<title>")
    assert start != -1, "no opening <title> tag in response"
    end = body.find("</title>", start)
    assert end != -1, "no closing </title> tag in response"
    return body[start + len("<title>") : end].strip()


@pytest.mark.django_db
def test_dashboard_title_tag_says_dashboard(mock_site_context, courses):
    """The dashboard's browser-tab title is 'Dashboard'."""
    user = UserFactory()
    client = _logged_in_client(user)
    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
    assert _extract_title(response.content.decode()) == "Dashboard"


@pytest.mark.django_db
def test_all_courses_title_tag_says_all_courses(mock_site_context, courses):
    """The all-courses page's browser-tab title is 'All Courses'."""
    user = UserFactory()
    client = _logged_in_client(user)
    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200
    assert _extract_title(response.content.decode()) == "All Courses"


@pytest.mark.django_db
def test_course_preview_title_tag_uses_course_title(mock_site_context, courses):
    """The course-preview page's browser-tab title matches the course title."""
    user = UserFactory()
    client = _logged_in_client(user)
    response = client.get(
        reverse(
            "student_interface:course_preview", kwargs={"course_slug": courses[0].slug}
        )
    )
    assert response.status_code == 200
    assert _extract_title(response.content.decode()) == courses[0].title
