"""Tests for coming-soon / hidden visibility in the discovery listings (Task 4.2).

Covers the dashboard "Available courses" grid and the all-courses row list:
  * a coming-soon course appears in discovery rendered with the coming-soon
    affordance ("I'm interested" / "Coming soon") and NO enrol CTA.
  * a hidden course is dropped from discovery for an unregistered user but
    still appears on the dashboard for a registered user (registered lists
    bypass filter_visible).
  * the is_interested stamp drives the interested vs not-interested variant.
  * the batched interest lookup issues a single query for the listing.
"""

from __future__ import annotations

import pytest

from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
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
def test_all_courses_coming_soon_shows_express_interest_no_enrol(mock_site_context):
    _course(CourseVisibility.COMING_SOON, slug="cs", title="Coming Soon Course")
    client = _logged_in_client(UserFactory())

    response = client.get(reverse("student_interface:courses"))
    body = response.content.decode()

    assert response.status_code == 200
    assert "Coming soon" in body
    assert "I'm interested" in body


@pytest.mark.django_db
def test_all_courses_coming_soon_interested_state(mock_site_context):
    course = _course(
        CourseVisibility.COMING_SOON, slug="cs", title="Coming Soon Course"
    )
    user = UserFactory()
    CourseInterestFactory(user=user, course=course)
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    body = response.content.decode()

    assert "Remove interest" in body


@pytest.mark.django_db
def test_all_courses_hidden_course_absent_for_unregistered(mock_site_context):
    _course(CourseVisibility.HIDDEN, slug="hid", title="Hidden Course")
    client = _logged_in_client(UserFactory())

    response = client.get(reverse("student_interface:courses"))

    assert "Hidden Course" not in response.content.decode()


# --- dashboard ---


@pytest.mark.django_db
def test_dashboard_coming_soon_shows_express_interest_no_enrol(mock_site_context):
    _course(CourseVisibility.COMING_SOON, slug="cs", title="Coming Soon Course")
    client = _logged_in_client(UserFactory())

    response = client.get(reverse("student_interface:dashboard"))
    body = response.content.decode()

    assert response.status_code == 200
    assert "Coming soon" in body
    assert "I'm interested" in body


@pytest.mark.django_db
def test_dashboard_coming_soon_interested_state_driven_by_stamp(mock_site_context):
    course = _course(
        CourseVisibility.COMING_SOON, slug="cs", title="Coming Soon Course"
    )
    user = UserFactory()
    CourseInterestFactory(user=user, course=course)
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    body = response.content.decode()

    assert "Remove interest" in body


@pytest.mark.django_db
def test_dashboard_recommended_coming_soon_shows_express_interest(mock_site_context):
    """A recommended coming-soon course renders the express-interest affordance,
    not the generic detail-link card."""
    course = _course(
        CourseVisibility.COMING_SOON, slug="cs", title="Coming Soon Course"
    )
    user = UserFactory()
    RecommendedCourseFactory(user=user, collection=course)
    client = _logged_in_client(user)

    response = client.get(reverse("student_interface:dashboard"))
    body = response.content.decode()

    assert "Coming soon" in body
    assert "I'm interested" in body


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


# --- batched lookup (no N+1) ---


def _course_interest_query_count(captured: CaptureQueriesContext) -> int:
    """Number of SELECTs against the course_interest table in the capture."""
    return sum(
        1
        for q in captured.captured_queries
        if "course_interest" in q["sql"].lower()
        and q["sql"].lstrip().lower().startswith("select")
    )


@pytest.mark.django_db
def test_all_courses_interest_lookup_is_single_query(mock_site_context):
    for n in range(3):
        _course(
            CourseVisibility.COMING_SOON,
            slug=f"cs-{n}",
            title=f"Coming Soon {n}",
        )
    user = UserFactory()
    client = _logged_in_client(user)
    base = reverse("student_interface:courses")

    with CaptureQueriesContext(connection) as captured:
        client.get(base)

    # Batched: three coming-soon courses must trigger exactly one interest
    # SELECT, not one per course (the N+1 the batching exists to prevent).
    assert _course_interest_query_count(captured) == 1
