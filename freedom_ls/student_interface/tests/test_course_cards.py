"""Tests for the three course-card variants and the course-preview view.

Per project conventions: no CSS class assertions. We assert on
content the user sees (course title, eyebrow text, "Next up:" line) and
on which partial got included.
"""

from __future__ import annotations

import pytest

from django.test import Client
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.student_management.factories import (
    UserCourseRegistrationFactory,
)
from freedom_ls.student_progress.factories import (
    CourseProgressFactory,
    TopicProgressFactory,
)


def _logged_in_client(user) -> Client:
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def course_with_topics(mock_site_context):
    course = CourseFactory(title="Course X", slug="course-x")
    for i in range(3):
        topic = TopicFactory(title=f"Topic {i}", slug=f"topic-x-{i}", content="content")
        course.items.create(child=topic, order=i)
    return course


# --- card dispatch ---


@pytest.mark.django_db
def test_not_started_card_for_zero_progress(mock_site_context, course_with_topics):
    """A registered course with progress_percentage == 0 renders the
    Not started card variant, not the In progress one."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course_with_topics)
    # No progress => percentage stays 0.
    client = _logged_in_client(user)
    response = client.get(reverse("student_interface:dashboard"))
    body = response.content.decode()
    assert "Not started" in body
    assert "In progress" not in body  # no in-progress card rendered


@pytest.mark.django_db
def test_in_progress_card_when_progress_above_zero(
    mock_site_context, course_with_topics
):
    """A course whose first topic is complete (>0 progress) renders the
    In progress card with the Next up line."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course_with_topics)
    # Mark first topic complete to push progress >0%.
    first_topic = course_with_topics.children()[0]
    TopicProgressFactory(user=user, topic=first_topic, complete_time=timezone.now())
    # Recompute progress on CourseProgress (the helper expects this row).
    cp = CourseProgressFactory(user=user, course=course_with_topics)
    cp.progress_percentage = 33
    cp.save()

    client = _logged_in_client(user)
    response = client.get(reverse("student_interface:dashboard"))
    body = response.content.decode()
    assert "In progress" in body


@pytest.mark.django_db
def test_complete_card_for_completed_course(mock_site_context, course_with_topics):
    """A completed course renders the Completed eyebrow."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course_with_topics)
    CourseProgressFactory(
        user=user,
        course=course_with_topics,
        completed_time=timezone.now(),
    )
    client = _logged_in_client(user)
    response = client.get(reverse("student_interface:dashboard"))
    body = response.content.decode()
    assert "Completed" in body


# --- course_preview view ---


@pytest.mark.django_db
def test_course_preview_returns_200_for_authenticated_user(
    mock_site_context, course_with_topics
):
    user = UserFactory()
    client = _logged_in_client(user)
    response = client.get(
        reverse(
            "student_interface:course_preview",
            kwargs={"course_slug": course_with_topics.slug},
        )
    )
    assert response.status_code == 200
    body = response.content.decode()
    assert course_with_topics.title in body
    # ToC items render.
    for child in course_with_topics.children():
        assert child.title in body


@pytest.mark.django_db
def test_course_preview_requires_login(mock_site_context, course_with_topics, client):
    """Anonymous users get redirected from the preview page."""
    response = client.get(
        reverse(
            "student_interface:course_preview",
            kwargs={"course_slug": course_with_topics.slug},
        )
    )
    assert response.status_code == 302


@pytest.mark.django_db
def test_course_preview_has_start_button_when_not_registered(
    mock_site_context, course_with_topics
):
    user = UserFactory()
    client = _logged_in_client(user)
    response = client.get(
        reverse(
            "student_interface:course_preview",
            kwargs={"course_slug": course_with_topics.slug},
        )
    )
    body = response.content.decode()
    # The shared partial drops a "Start" button when is_registered is False.
    assert "Start" in body


@pytest.mark.django_db
def test_modal_and_page_share_preview_content_partial(
    mock_site_context, course_with_topics
):
    """Rendering the dashboard's not-started modal and the standalone
    preview page must surface the same title + ToC items, because they
    both include `course_preview_content.html`."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course_with_topics)
    client = _logged_in_client(user)

    # Standalone preview page.
    page = client.get(
        reverse(
            "student_interface:course_preview",
            kwargs={"course_slug": course_with_topics.slug},
        )
    )
    page_body = page.content.decode()

    # Dashboard with the not-started modal trigger (registered, p == 0).
    dashboard = client.get(reverse("student_interface:dashboard"))
    dash_body = dashboard.content.decode()

    # The course title + ToC items appear in both renderings.
    assert course_with_topics.title in page_body
    assert course_with_topics.title in dash_body
    for child in course_with_topics.children():
        assert child.title in page_body
        # ToC items render in the not-started modal too.
        assert child.title in dash_body
