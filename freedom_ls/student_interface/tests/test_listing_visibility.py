"""Tests for coming-soon / hidden visibility in the discovery listings (Task 4.2).

Covers the dashboard "Available courses" grid and the all-courses row list:
  * a coming-soon course appears in discovery as an ordinary card/row — a plain
    link to the course detail page carrying a "Coming soon" chip — with NO
    express-interest CTA and NO enrol control (the CTA lives only on the course
    detail page).
  * a hidden course is dropped from discovery for an unregistered user but
    still appears on the dashboard for a registered user (registered lists
    bypass filter_visible).
  * the public home page (anonymous GET /) drops hidden courses while still
    showing published and coming-soon courses (the anonymous filter_visible
    branch excludes only HIDDEN).
"""

from __future__ import annotations

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import Course, CourseVisibility
from freedom_ls.course_interest.factories import CourseInterestFactory
from freedom_ls.student_management.factories import (
    RecommendedCourseFactory,
    UserCourseRegistrationFactory,
)


def _logged_in_client(user) -> Client:
    """Build a Client logged in as `user`. Local helper — do not lift across files."""
    client = Client()
    client.force_login(user)
    return client


def _course(visibility: str, *, slug: str, title: str) -> Course:
    """A course with the given visibility and one topic item."""
    course: Course = CourseFactory(title=title, slug=slug, visibility=visibility)
    topic = TopicFactory(title=f"{slug}-t", slug=f"{slug}-topic", content="content")
    course.items.create(child=topic, order=0)
    return course


# --- all_courses ---


@pytest.mark.django_db
def test_all_courses_coming_soon_is_plain_detail_link_no_cta(mock_site_context):
    """A coming-soon course lists as an ordinary row: a "Coming soon" chip and a
    plain link to the course detail page, with no express-interest CTA."""
    _course(CourseVisibility.COMING_SOON, slug="cs", title="Coming Soon Course")
    client = _logged_in_client(UserFactory())

    response = client.get(reverse("student_interface:courses"))
    body = response.content.decode()

    detail_url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": "cs"}
    )
    assert response.status_code == 200
    assert "Coming soon" in body
    assert f'href="{detail_url}"' in body
    assert "I'm interested" not in body


@pytest.mark.django_db
def test_all_courses_coming_soon_no_cta_even_when_interested(mock_site_context):
    """The listing never shows the express-interest CTA, even for a learner who
    has already expressed interest (that control lives only on the detail page)."""
    course = _course(
        CourseVisibility.COMING_SOON, slug="cs", title="Coming Soon Course"
    )
    user = UserFactory()
    CourseInterestFactory(user=user, course=course)
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    body = response.content.decode()

    assert "I'm interested" not in body
    assert "Remove interest" not in body


@pytest.mark.django_db
def test_all_courses_hidden_course_absent_for_unregistered(mock_site_context):
    _course(CourseVisibility.HIDDEN, slug="hid", title="Hidden Course")
    client = _logged_in_client(UserFactory())

    response = client.get(reverse("student_interface:courses"))

    assert "Hidden Course" not in response.content.decode()


@pytest.mark.django_db
def test_all_courses_coming_soon_registered_keeps_registered_status(mock_site_context):
    """A learner registered for a coming-soon course keeps their registered listing
    status — coming-soon exempts registered users, so no express-interest CTA."""
    course = _course(
        CourseVisibility.COMING_SOON, slug="cs", title="Coming Soon Course"
    )
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course, is_active=True)
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    body = response.content.decode()

    assert response.status_code == 200
    assert "Coming Soon Course" in body
    assert "I'm interested" not in body


# --- dashboard ---


@pytest.mark.django_db
def test_dashboard_coming_soon_is_plain_detail_link_no_cta(mock_site_context):
    """A coming-soon course lists as an ordinary card: a "Coming soon" chip and a
    plain link to the course detail page, with no express-interest CTA."""
    _course(CourseVisibility.COMING_SOON, slug="cs", title="Coming Soon Course")
    client = _logged_in_client(UserFactory())

    response = client.get(reverse("student_interface:dashboard"))
    body = response.content.decode()

    detail_url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": "cs"}
    )
    assert response.status_code == 200
    assert "Coming soon" in body
    assert f'href="{detail_url}"' in body
    assert "I'm interested" not in body


@pytest.mark.django_db
def test_dashboard_coming_soon_no_cta_even_when_interested(mock_site_context):
    """The dashboard never shows the express-interest CTA, even for a learner who
    has already expressed interest (that control lives only on the detail page)."""
    course = _course(
        CourseVisibility.COMING_SOON, slug="cs", title="Coming Soon Course"
    )
    user = UserFactory()
    CourseInterestFactory(user=user, course=course)
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    body = response.content.decode()

    assert "I'm interested" not in body
    assert "Remove interest" not in body


@pytest.mark.django_db
def test_dashboard_recommended_coming_soon_is_plain_detail_link_no_cta(
    mock_site_context,
):
    """A recommended coming-soon course renders as a plain detail-link card with a
    "Coming soon" chip and no express-interest CTA."""
    course = _course(
        CourseVisibility.COMING_SOON, slug="cs", title="Coming Soon Course"
    )
    user = UserFactory()
    RecommendedCourseFactory(user=user, collection=course)
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    body = response.content.decode()

    detail_url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": "cs"}
    )
    assert "Coming soon" in body
    assert f'href="{detail_url}"' in body
    assert "I'm interested" not in body


@pytest.mark.django_db
def test_dashboard_hidden_recommended_absent_for_unregistered(mock_site_context):
    """A hidden recommended course must not leak as a card for an unregistered
    user — recommendations bypass the available-courses filter_visible pass, so
    the dashboard view must drop hidden-and-unregistered recommendations."""
    course = _course(CourseVisibility.HIDDEN, slug="hid", title="Hidden Recommended")
    user = UserFactory()
    RecommendedCourseFactory(user=user, collection=course)
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))

    assert "Hidden Recommended" not in response.content.decode()


@pytest.mark.django_db
def test_dashboard_hidden_recommended_present_for_registered(mock_site_context):
    """A hidden recommended course the user IS registered for still appears —
    the "registered keeps access" rule wins over the hidden exclusion."""
    course = _course(CourseVisibility.HIDDEN, slug="hid", title="Hidden Recommended")
    user = UserFactory()
    RecommendedCourseFactory(user=user, collection=course)
    UserCourseRegistrationFactory(user=user, collection=course, is_active=True)
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))

    assert "Hidden Recommended" in response.content.decode()


@pytest.mark.django_db
def test_dashboard_hidden_absent_for_unregistered(mock_site_context):
    _course(CourseVisibility.HIDDEN, slug="hid", title="Hidden Course")
    client = _logged_in_client(UserFactory())

    response = client.get(reverse("student_interface:dashboard"))

    assert "Hidden Course" not in response.content.decode()


@pytest.mark.django_db
def test_dashboard_hidden_present_for_registered_user(mock_site_context):
    course = _course(CourseVisibility.HIDDEN, slug="hid", title="Hidden Course")
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course, is_active=True)
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))

    assert "Hidden Course" in response.content.decode()


# --- public home page (anonymous GET /) ---


@pytest.mark.django_db
def test_dashboard_shows_published_course_for_anonymous(mock_site_context):
    """Positive control: the anonymous public home page renders published courses
    in its discovery grid, so the hidden-course absence assertion below is
    meaningful (the grid is not simply empty)."""
    _course(CourseVisibility.PUBLISHED, slug="pub", title="Published Course")

    response = Client().get(reverse("student_interface:dashboard"))

    assert response.status_code == 200
    assert "Published Course" in response.content.decode()


@pytest.mark.django_db
def test_dashboard_hidden_absent_for_anonymous(mock_site_context):
    """A hidden course must never appear on the public home page for an anonymous
    visitor — the anonymous filter_visible branch excludes HIDDEN."""
    _course(CourseVisibility.HIDDEN, slug="hid", title="Hidden Course")

    response = Client().get(reverse("student_interface:dashboard"))

    assert "Hidden Course" not in response.content.decode()


@pytest.mark.django_db
def test_dashboard_coming_soon_present_for_anonymous(mock_site_context):
    """A coming-soon course still appears on the public home page for an anonymous
    visitor (with its "Coming soon" chip) — the exclusion is specific to HIDDEN."""
    _course(CourseVisibility.COMING_SOON, slug="cs", title="Coming Soon Course")

    response = Client().get(reverse("student_interface:dashboard"))
    body = response.content.decode()

    assert "Coming Soon Course" in body
    assert "Coming soon" in body
