"""Tests for the three course-card variants and the course-detail view.

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
    assert 'value="0"' in body
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


# --- course_detail view ---


@pytest.mark.django_db
def test_course_detail_returns_200_for_authenticated_user(
    mock_site_context, course_with_topics
):
    user = UserFactory()
    client = _logged_in_client(user)
    response = client.get(
        reverse(
            "student_interface:course_detail",
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
def test_course_detail_requires_login(mock_site_context, course_with_topics, client):
    """Anonymous users get redirected from the detail page."""
    response = client.get(
        reverse(
            "student_interface:course_detail",
            kwargs={"course_slug": course_with_topics.slug},
        )
    )
    assert response.status_code == 302


@pytest.mark.django_db
def test_course_detail_shows_enrol_and_start_for_unregistered_user(
    mock_site_context, course_with_topics
):
    """An unregistered user sees 'Enrol & start' CTA on the detail page."""
    user = UserFactory()
    client = _logged_in_client(user)
    response = client.get(
        reverse(
            "student_interface:course_detail",
            kwargs={"course_slug": course_with_topics.slug},
        )
    )
    body = response.content.decode()
    assert "Enrol &amp; start" in body or "Enrol & start" in body


@pytest.mark.django_db
def test_course_detail_enrol_cta_links_to_register_for_course_when_unregistered(
    mock_site_context, course_with_topics
):
    """The CTA for an unregistered user links to the register_for_course URL."""
    user = UserFactory()
    client = _logged_in_client(user)
    response = client.get(
        reverse(
            "student_interface:course_detail",
            kwargs={"course_slug": course_with_topics.slug},
        )
    )
    body = response.content.decode()
    register_url = reverse(
        "student_interface:register_for_course",
        kwargs={"course_slug": course_with_topics.slug},
    )
    assert register_url in body


@pytest.mark.django_db
def test_course_detail_has_start_button_when_registered_zero_progress(
    mock_site_context, course_with_topics
):
    """A registered learner with 0 progress lands on the detail page
    and sees a Start course button pointing to the first item."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course_with_topics)
    client = _logged_in_client(user)
    response = client.get(
        reverse(
            "student_interface:course_detail",
            kwargs={"course_slug": course_with_topics.slug},
        )
    )
    body = response.content.decode()
    first_item_url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course_with_topics.slug, "index": 1},
    )
    assert "Start course" in body
    assert first_item_url in body


@pytest.mark.django_db
def test_course_detail_shows_continue_when_registered_with_progress(
    mock_site_context, course_with_topics
):
    """A registered learner with partial (>0) progress and no completion
    sees a 'Continue' CTA."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course_with_topics)
    cp = CourseProgressFactory(user=user, course=course_with_topics)
    cp.progress_percentage = 50
    cp.completed_time = None
    cp.save()

    client = _logged_in_client(user)
    response = client.get(
        reverse(
            "student_interface:course_detail",
            kwargs={"course_slug": course_with_topics.slug},
        )
    )
    body = response.content.decode()
    assert "Continue" in body


@pytest.mark.django_db
def test_course_detail_shows_review_course_when_completed(
    mock_site_context, course_with_topics
):
    """A registered learner who has completed the course sees a
    'Review course' CTA."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course_with_topics)
    CourseProgressFactory(
        user=user,
        course=course_with_topics,
        completed_time=timezone.now(),
    )

    client = _logged_in_client(user)
    response = client.get(
        reverse(
            "student_interface:course_detail",
            kwargs={"course_slug": course_with_topics.slug},
        )
    )
    body = response.content.decode()
    assert "Review course" in body


@pytest.mark.django_db
def test_course_detail_renders_breadcrumbs(mock_site_context, course_with_topics):
    """The detail page renders breadcrumbs including the 'All courses' link
    and the current course title."""
    user = UserFactory()
    client = _logged_in_client(user)
    response = client.get(
        reverse(
            "student_interface:course_detail",
            kwargs={"course_slug": course_with_topics.slug},
        )
    )
    body = response.content.decode()
    all_courses_url = reverse("student_interface:courses")
    assert all_courses_url in body
    assert "All courses" in body
    assert course_with_topics.title in body


@pytest.mark.django_db
def test_course_detail_renders_lesson_count_in_stats(
    mock_site_context, course_with_topics
):
    """The detail page stats strip always shows the lesson count."""
    user = UserFactory()
    client = _logged_in_client(user)
    response = client.get(
        reverse(
            "student_interface:course_detail",
            kwargs={"course_slug": course_with_topics.slug},
        )
    )
    body = response.content.decode()
    # course_with_topics has 3 topics
    assert "3 lesson" in body


@pytest.mark.django_db
def test_course_detail_omits_difficulty_when_not_set(
    mock_site_context, course_with_topics
):
    """When difficulty is not set, the detail page shows no difficulty text."""
    user = UserFactory()
    client = _logged_in_client(user)
    response = client.get(
        reverse(
            "student_interface:course_detail",
            kwargs={"course_slug": course_with_topics.slug},
        )
    )
    body = response.content.decode()
    # course_with_topics has no difficulty set — none of the difficulty display values should appear
    for label in ("Beginner", "Intermediate", "Advanced", "All levels"):
        assert label not in body


@pytest.mark.django_db
def test_course_detail_omits_duration_when_not_set(
    mock_site_context, course_with_topics
):
    """When estimated_duration is not set, the detail page shows no duration."""
    user = UserFactory()
    client = _logged_in_client(user)
    response = client.get(
        reverse(
            "student_interface:course_detail",
            kwargs={"course_slug": course_with_topics.slug},
        )
    )
    body = response.content.decode()
    # The duration stat is omitted entirely — its "Duration" label never renders.
    assert "Duration" not in body


@pytest.mark.django_db
def test_course_detail_omits_learning_outcomes_section_when_not_set(
    mock_site_context, course_with_topics
):
    """When learning_outcomes is empty, the 'What you'll learn' section is absent."""
    user = UserFactory()
    client = _logged_in_client(user)
    response = client.get(
        reverse(
            "student_interface:course_detail",
            kwargs={"course_slug": course_with_topics.slug},
        )
    )
    body = response.content.decode()
    assert "What you'll learn" not in body


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
    assert 'value="0"' in body
    assert first_item_url in body


@pytest.mark.django_db
def test_not_registered_card_links_to_course_detail(
    mock_site_context, course_with_topics
):
    """A not-registered course card links to the course_detail URL (not a modal)."""
    user = UserFactory()
    RecommendedCourseFactory(user=user, collection=course_with_topics)
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    body = response.content.decode()

    detail_url = reverse(
        "student_interface:course_detail",
        kwargs={"course_slug": course_with_topics.slug},
    )
    assert detail_url in body


@pytest.mark.django_db
def test_not_registered_card_has_no_modal_trigger(
    mock_site_context, course_with_topics
):
    """The not-registered card links to course_detail, not a modal, on the dashboard."""
    user = UserFactory()
    RecommendedCourseFactory(user=user, collection=course_with_topics)
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    body = response.content.decode()

    detail_url = reverse(
        "student_interface:course_detail",
        kwargs={"course_slug": course_with_topics.slug},
    )
    # The card links to the detail page via a real anchor...
    assert f'href="{detail_url}"' in body
    # ...and no modal component is rendered (the c-modal root carries x-data="modal").
    assert 'x-data="modal"' not in body
