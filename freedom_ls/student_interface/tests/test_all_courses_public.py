"""Tests for Phase 3: public all_courses view + access badge.

Covers:
- Anonymous access (no login redirect)
- Free vs. application-gated badge labels in rendered rows
- Anonymous rows suppress the "Not registered" eyebrow
- Site isolation: courses on another site are absent
"""

from __future__ import annotations

import pytest

from django.contrib.sites.models import Site
from django.test import Client, override_settings
from django.urls import reverse

from freedom_ls.content_engine.factories import CourseFactory, TopicFactory


@pytest.mark.django_db
def test_all_courses_anonymous_returns_200(mock_site_context):
    """Anonymous GET /courses/ returns 200 — no login redirect."""
    client = Client()
    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_all_courses_anonymous_lists_site_courses(mock_site_context):
    """Anonymous visitors see all site courses listed."""
    course = CourseFactory(title="Intro to Django", slug="intro-to-django")
    topic = TopicFactory(slug="t1", content="hi")
    course.items.create(child=topic, order=0)

    client = Client()
    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200
    assert "Intro to Django" in response.content.decode()


@pytest.mark.django_db
@override_settings(
    COURSE_ACCESS_BACKEND="freedom_ls.course_applications.backends.ApplicationCourseAccessBackend"
)
def test_all_courses_free_course_row_shows_free_badge(mock_site_context):
    """A free course row shows a 'Free' access badge for anonymous users."""
    from freedom_ls.course_access.loader import get_course_access_backend

    # override_settings already activated by decorator; re-clear so the correct
    # backend is resolved (the autouse fixture clears before the decorator runs).
    get_course_access_backend.cache_clear()

    # Default access_config is free (no access_type set)
    course = CourseFactory(title="Free Course", slug="free-course")
    topic = TopicFactory(slug="t-free", content="content")
    course.items.create(child=topic, order=0)

    client = Client()
    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200
    body = response.content.decode()
    assert "Free" in body
    assert "By application" not in body


@pytest.mark.django_db
@override_settings(
    COURSE_ACCESS_BACKEND="freedom_ls.course_applications.backends.ApplicationCourseAccessBackend"
)
def test_all_courses_gated_course_row_shows_by_application_badge(mock_site_context):
    """An application-gated course row shows 'By application' badge for anonymous users."""
    from freedom_ls.course_access.loader import get_course_access_backend

    # override_settings already activated by decorator; re-clear so the correct
    # backend is resolved (the autouse fixture clears before the decorator runs).
    get_course_access_backend.cache_clear()

    gated_course = CourseFactory(
        title="Gated Course",
        slug="gated-course",
        access_config={"access_type": "application_gated"},
    )
    topic = TopicFactory(slug="t-gated", content="content")
    gated_course.items.create(child=topic, order=0)

    client = Client()
    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200
    body = response.content.decode()
    assert "By application" in body
    assert "Free" not in body


@pytest.mark.django_db
def test_all_courses_anonymous_not_registered_row_has_no_not_registered_eyebrow(
    mock_site_context,
):
    """Anonymous not-registered rows do not render the 'Not registered' eyebrow text."""
    CourseFactory(title="Some Course", slug="some-course")

    client = Client()
    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200
    assert "Not registered" not in response.content.decode()


@pytest.mark.django_db
def test_all_courses_authenticated_not_registered_row_shows_not_registered_eyebrow(
    mock_site_context,
):
    """Authenticated users still see the 'Not registered' eyebrow on unregistered rows."""
    from freedom_ls.accounts.factories import UserFactory

    CourseFactory(title="Some Course", slug="some-course")
    user = UserFactory()
    client = Client()
    client.force_login(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200
    assert "Not registered" in response.content.decode()


@pytest.mark.django_db
def test_all_courses_site_isolation(mock_site_context):
    """A course on another site is absent from the anonymous catalogue."""
    other_site = Site.objects.create(name="OtherSite", domain="other.example.com")

    # Course on our site (mock_site_context site)
    CourseFactory(title="Our Course", slug="our-course")

    # Course on another site — override the site after creation
    other_course = CourseFactory(title="Other Site Course", slug="other-site-course")
    other_course.site = other_site
    other_course.save()

    client = Client()
    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200
    body = response.content.decode()
    assert "Our Course" in body
    assert "Other Site Course" not in body
