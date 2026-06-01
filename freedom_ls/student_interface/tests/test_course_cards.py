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
    RecommendedCourseFactory,
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
def test_registered_card_for_zero_progress(mock_site_context, course_with_topics):
    """A registered course with progress_percentage == 0 renders the
    Registered card variant, not the In progress one. The old ambiguous
    "Not started" label (shared with unregistered courses) is retired."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course_with_topics)
    # No progress => percentage stays 0.
    client = _logged_in_client(user)
    response = client.get(reverse("student_interface:dashboard"))
    body = response.content.decode()
    assert "Registered" in body
    assert "In progress" not in body  # no in-progress card rendered
    assert "Not started" not in body  # retired label


@pytest.mark.django_db
def test_registered_card_shows_empty_progress_bar(
    mock_site_context, course_with_topics
):
    """The Registered card always renders an empty (0%) progress bar so it
    visually anchors next to in-progress cards in a mixed grid row."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course_with_topics)
    client = _logged_in_client(user)
    response = client.get(reverse("student_interface:dashboard"))
    body = response.content.decode()
    assert "Registered" in body
    assert 'aria-valuenow="0"' in body
    assert "0%" in body


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


@pytest.mark.django_db
def test_not_registered_card_shows_not_registered_label(
    mock_site_context, course_with_topics
):
    """A recommended (unregistered) course on the dashboard shows the
    "Not registered" status — distinct from a registered-but-unstarted
    course — instead of the old ambiguous "Not started"."""
    user = UserFactory()
    RecommendedCourseFactory(user=user, collection=course_with_topics)
    client = _logged_in_client(user)
    response = client.get(reverse("student_interface:dashboard"))
    body = response.content.decode()
    assert "Not registered" in body
    assert "Not started" not in body


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
def test_registered_card_does_not_link_to_register_url(
    mock_site_context, course_with_topics
):
    """A registered learner's card never links to the registration URL —
    registering again would be a no-op redirect. Registered courses render
    the progress card (no preview modal), so the register link is absent."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course_with_topics)
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    body = response.content.decode()

    register_url = reverse(
        "student_interface:register_for_course",
        kwargs={"course_slug": course_with_topics.slug},
    )
    assert register_url not in body


@pytest.mark.django_db
def test_course_preview_has_start_button_when_registered_zero_progress(
    mock_site_context, course_with_topics
):
    """Bug: a registered learner with 0 progress lands on the preview page
    and must see a Start button taking them into the course's first item.
    Previously the partial only rendered Start for unregistered users, so a
    registered-but-not-yet-started learner had no way forward from preview."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course_with_topics)
    client = _logged_in_client(user)
    response = client.get(
        reverse(
            "student_interface:course_preview",
            kwargs={"course_slug": course_with_topics.slug},
        )
    )
    body = response.content.decode()
    first_item_url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course_with_topics.slug, "index": 1},
    )
    assert "Start" in body
    assert first_item_url in body


@pytest.mark.django_db
def test_registered_zero_progress_card_links_title_to_first_item(
    mock_site_context, course_with_topics
):
    """A registered 0-progress course renders the progress card (not a modal):
    the "Registered" eyebrow, a 0% progress bar, and a title that links
    straight to the first course item via the "Next up" target."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course_with_topics)
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    body = response.content.decode()

    first_item_url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course_with_topics.slug, "index": 1},
    )
    assert "Registered" in body
    assert 'aria-valuenow="0"' in body
    assert first_item_url in body


@pytest.mark.django_db
def test_not_started_modal_shows_start_for_unregistered_user(
    mock_site_context, course_with_topics
):
    """The converse of the bug: a recommended (unregistered) course on the
    dashboard renders the Start button linking to the registration URL."""
    user = UserFactory()
    RecommendedCourseFactory(user=user, collection=course_with_topics)
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    body = response.content.decode()

    register_url = reverse(
        "student_interface:register_for_course",
        kwargs={"course_slug": course_with_topics.slug},
    )
    assert register_url in body


@pytest.mark.django_db
def test_modal_and_page_share_preview_content_partial(
    mock_site_context, course_with_topics
):
    """Rendering the dashboard's not-started modal and the standalone
    preview page must surface the same title + ToC items, because they
    both include `course_preview_content.html`.

    The modal only renders for unregistered (recommended) courses — a
    registered course gets the progress card instead — so the dashboard
    course here is a recommendation."""
    user = UserFactory()
    RecommendedCourseFactory(user=user, collection=course_with_topics)
    client = _logged_in_client(user)

    # Standalone preview page.
    page = client.get(
        reverse(
            "student_interface:course_preview",
            kwargs={"course_slug": course_with_topics.slug},
        )
    )
    page_body = page.content.decode()

    # Dashboard with the not-started modal trigger (unregistered recommendation).
    dashboard = client.get(reverse("student_interface:dashboard"))
    dash_body = dashboard.content.decode()

    # The course title + ToC items appear in both renderings.
    assert course_with_topics.title in page_body
    assert course_with_topics.title in dash_body
    for child in course_with_topics.children():
        assert child.title in page_body
        # ToC items render in the not-started modal too.
        assert child.title in dash_body
