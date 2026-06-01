"""Tests for the browser-tab <title> tags across the student-facing pages.

Covers the dashboard, all-courses, and course-preview pages (Bug 2).
"""

from __future__ import annotations

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory


def _logged_in_client(user) -> Client:
    """Build a Client logged in as `user`. Local helper — do not lift across files."""
    client = Client()
    client.force_login(user)
    return client


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
