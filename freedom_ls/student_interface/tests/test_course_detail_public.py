"""Tests for Phase 4: public course_detail view for anonymous users.

Covers:
- Anonymous GET of a free course detail → 200, CTA "Enrol for free" with access URL
- Anonymous GET of a gated course detail → 200, CTA "Apply now" with apply URL
- ToC items render as BLOCKED (no URLs) for anonymous viewers
- Regression: no crash on application-gated course for anonymous user
"""

from __future__ import annotations

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.student_interface.utils import BLOCKED


def _free_course() -> Course:
    """Create a free course with one topic."""
    course: Course = CourseFactory(
        slug="anon-free-course",
        title="Free Course",
        access_config={"access_type": "free"},
    )
    topic = TopicFactory(title="Topic 1", slug="anon-free-topic-1", content="content")
    course.items.create(child=topic, order=0)
    return course


def _gated_course() -> Course:
    """Create an application-gated course with one topic."""
    course: Course = CourseFactory(
        slug="anon-gated-course",
        title="Gated Course",
        access_config={"access_type": "application_gated"},
    )
    topic = TopicFactory(title="Topic 1", slug="anon-gated-topic-1", content="content")
    course.items.create(child=topic, order=0)
    return course


# ---------------------------------------------------------------------------
# Anonymous access — free course
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_anonymous_free_course_detail_returns_200(mock_site_context):
    """Anonymous GET of a free course detail returns 200 — no login redirect."""
    course = _free_course()
    client = Client()

    url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_anonymous_free_course_detail_cta_label_is_enrol_for_free(mock_site_context):
    """Anonymous user on a free course detail page sees 'Enrol for free' CTA."""
    course = _free_course()
    client = Client()

    url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert "Enrol for free" in response.content.decode()


@pytest.mark.django_db
def test_anonymous_free_course_detail_cta_href_is_access_url(mock_site_context):
    """Anonymous user on a free course detail page: CTA href points to initiate_course_access."""
    course = _free_course()
    client = Client()

    url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    access_url = reverse(
        "student_interface:initiate_course_access",
        kwargs={"course_slug": course.slug},
    )
    assert access_url in response.content.decode()


# ---------------------------------------------------------------------------
# Anonymous access — application-gated course
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_anonymous_gated_course_detail_returns_200(mock_site_context):
    """Anonymous GET of a gated course detail returns 200 — no crash, no login redirect.

    Regression test: ApplicationCourseAccessBackend.get_access previously crashed
    for anonymous users due to an unsafe application DB query.
    """
    course = _gated_course()
    client = Client()

    url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_anonymous_gated_course_detail_cta_label_is_apply_now(mock_site_context):
    """Anonymous user on a gated course detail page sees 'Apply now' CTA."""
    course = _gated_course()
    client = Client()

    url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert "Apply now" in response.content.decode()


@pytest.mark.django_db
def test_anonymous_gated_course_detail_cta_href_is_apply_url(mock_site_context):
    """Anonymous user on a gated course detail page: CTA href points to apply view."""
    course = _gated_course()
    client = Client()

    url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    apply_url = reverse(
        "course_applications:apply", kwargs={"course_slug": course.slug}
    )
    assert apply_url in response.content.decode()


@pytest.mark.django_db
def test_anonymous_gated_course_detail_shows_by_application(mock_site_context):
    """Anonymous gated course detail shows 'By application' near the CTA."""
    course = _gated_course()
    client = Client()

    url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert "By application" in response.content.decode()


# ---------------------------------------------------------------------------
# ToC items blocked for anonymous viewers
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_anonymous_free_course_detail_toc_items_all_blocked(mock_site_context):
    """All ToC items are BLOCKED for an anonymous viewer on a free course."""
    course = _free_course()
    client = Client()

    url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert response.status_code == 200
    children = response.context["children"]
    assert children, "Expected at least one ToC item"
    for child in children:
        assert child["status"] == BLOCKED


@pytest.mark.django_db
def test_anonymous_gated_course_detail_toc_items_all_blocked(mock_site_context):
    """All ToC items are BLOCKED for an anonymous viewer on a gated course."""
    course = _gated_course()
    client = Client()

    url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert response.status_code == 200
    children = response.context["children"]
    assert children, "Expected at least one ToC item"
    for child in children:
        assert child["status"] == BLOCKED


@pytest.mark.django_db
def test_anonymous_free_course_detail_toc_items_have_no_url(mock_site_context):
    """BLOCKED ToC items for an anonymous viewer carry no URL."""
    course = _free_course()
    client = Client()

    url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    children = response.context["children"]
    for child in children:
        assert not child.get("url"), (
            f"Expected no URL on BLOCKED item '{child['title']}'"
        )
