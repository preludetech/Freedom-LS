"""Tests for where the course-price component is placed: the course card, the
course row, the course page's stats strip and its sign-up panel.

Per project conventions: no CSS class assertions. We assert on the
component's ``data-testid`` and on visible text.
"""

from __future__ import annotations

from decimal import Decimal
from typing import cast

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import Course, CourseVisibility
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory

PRICE_TESTID = 'data-testid="course-price"'


def _priced(course_with_topic, **kwargs: object) -> Course:
    return cast(
        "Course",
        course_with_topic(
            price_kind="fixed",
            price_amount=Decimal("1499.00"),
            price_currency="ZAR",
            **kwargs,
        ),
    )


def _priced_coming_soon(*, slug: str, title: str) -> Course:
    course: Course = CourseFactory(
        title=title,
        slug=slug,
        visibility=CourseVisibility.COMING_SOON,
        price_kind="fixed",
        price_amount=Decimal("1499.00"),
        price_currency="ZAR",
    )
    topic = TopicFactory(title=f"{slug}-t", slug=f"{slug}-topic", content="content")
    course.items.create(child=topic, order=0)
    return course


# ---------------------------------------------------------------------------
# Course card (dashboard discovery sections)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboard_card_shows_price_to_anonymous_visitor(
    mock_site_context, course_with_topic
):
    _priced(course_with_topic)
    client = Client()

    response = client.get(reverse("learner_interface:dashboard"))

    assert PRICE_TESTID in response.content.decode()


@pytest.mark.django_db
def test_dashboard_card_shows_price_to_signed_in_not_registered_visitor(
    mock_site_context, course_with_topic, logged_in_client
):
    _priced(course_with_topic)
    client = logged_in_client(UserFactory())

    response = client.get(reverse("learner_interface:dashboard"))

    assert PRICE_TESTID in response.content.decode()


@pytest.mark.django_db
def test_dashboard_card_hides_price_for_registered_learner(
    mock_site_context, course_with_topic, logged_in_client
):
    course = _priced(course_with_topic)
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))

    assert PRICE_TESTID not in response.content.decode()


@pytest.mark.django_db
def test_dashboard_card_shows_price_for_coming_soon_course(mock_site_context):
    _priced_coming_soon(slug="coming-soon-priced", title="Coming Soon Priced")
    client = Client()

    response = client.get(reverse("learner_interface:dashboard"))

    assert PRICE_TESTID in response.content.decode()


@pytest.mark.django_db
def test_dashboard_card_with_no_price_shows_no_price_component(
    mock_site_context, course_with_topic
):
    course_with_topic()
    client = Client()

    response = client.get(reverse("learner_interface:dashboard"))

    assert PRICE_TESTID not in response.content.decode()


# ---------------------------------------------------------------------------
# Course row (all-courses list)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_all_courses_row_shows_price_to_anonymous_visitor(
    mock_site_context, course_with_topic
):
    _priced(course_with_topic)
    client = Client()

    response = client.get(reverse("learner_interface:courses"))

    assert PRICE_TESTID in response.content.decode()


@pytest.mark.django_db
def test_all_courses_row_shows_price_to_signed_in_not_registered_visitor(
    mock_site_context, course_with_topic, logged_in_client
):
    _priced(course_with_topic)
    client = logged_in_client(UserFactory())

    response = client.get(reverse("learner_interface:courses"))

    assert PRICE_TESTID in response.content.decode()


@pytest.mark.django_db
def test_all_courses_row_hides_price_for_registered_learner(
    mock_site_context, course_with_topic, logged_in_client
):
    course = _priced(course_with_topic)
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:courses"))

    assert PRICE_TESTID not in response.content.decode()


@pytest.mark.django_db
def test_all_courses_row_shows_price_for_coming_soon_course(mock_site_context):
    _priced_coming_soon(slug="coming-soon-priced-row", title="Coming Soon Priced Row")
    client = Client()

    response = client.get(reverse("learner_interface:courses"))

    assert PRICE_TESTID in response.content.decode()


@pytest.mark.django_db
def test_all_courses_row_with_no_price_shows_no_price_component(
    mock_site_context, course_with_topic
):
    course_with_topic()
    client = Client()

    response = client.get(reverse("learner_interface:courses"))

    assert PRICE_TESTID not in response.content.decode()


# ---------------------------------------------------------------------------
# Course page: stats strip and sign-up panel
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_course_detail_shows_price_twice_for_anonymous_visitor(
    mock_site_context, course_with_topic
):
    """The stats-strip cell and the sign-up panel each render their own
    price, so an anonymous (not-registered) visitor sees two."""
    course = _priced(course_with_topic)
    client = Client()

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    body = client.get(url).content.decode()

    assert body.count(PRICE_TESTID) == 2


@pytest.mark.django_db
def test_course_detail_shows_price_once_for_registered_learner(
    mock_site_context, course_with_topic, logged_in_client
):
    """The sign-up panel price is withheld once registered, so only the
    stats-strip cell remains."""
    course = _priced(course_with_topic)
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course)
    client = logged_in_client(user)

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    body = client.get(url).content.decode()

    assert body.count(PRICE_TESTID) == 1


@pytest.mark.django_db
def test_course_detail_application_gated_priced_course_still_shows_apply_cta(
    mock_site_context, course_with_topic
):
    course = _priced(course_with_topic, access_type="application_gated")
    client = Client()

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    body = client.get(url).content.decode()

    assert "By application" in body
    assert "Apply now" in body
    assert PRICE_TESTID in body


@pytest.mark.django_db
def test_course_detail_with_no_price_shows_no_price_component(
    mock_site_context, course_with_topic
):
    course = course_with_topic()
    client = Client()

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    body = client.get(url).content.decode()

    assert PRICE_TESTID not in body
