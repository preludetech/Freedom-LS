"""Tests for the anonymous home page variant.

They cover:
- Anonymous GET / returns 200 (no login redirect)
- Anonymous home shows hero headline + Browse-all CTA
- Anonymous home does NOT show authenticated-only content
- Anonymous home shows Login/Sign-up buttons carrying next=/
- Anonymous GET / does NOT call backend.get_dashboard_contributions
- Authenticated dashboard unchanged (hero absent for auth user)
"""

from __future__ import annotations

from unittest import mock

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import SiteSignupPolicyFactory, UserFactory


@pytest.mark.django_db
def test_anonymous_dashboard_returns_200(mock_site_context):
    """Anonymous GET / must return 200, not a login redirect."""
    client = Client()
    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_anonymous_dashboard_contains_hero_headline(mock_site_context):
    """Anonymous home page shows the hero value-prop headline."""
    client = Client()
    response = client.get(reverse("student_interface:dashboard"))
    body = response.content.decode()
    # The hero headline should appear for anonymous users
    assert "Teach the way your learners need" in body


@pytest.mark.django_db
def test_anonymous_dashboard_contains_browse_all_courses_cta(mock_site_context):
    """Anonymous home page shows a 'Browse all courses' link to the catalogue."""
    client = Client()
    response = client.get(reverse("student_interface:dashboard"))
    body = response.content.decode()
    courses_url = reverse("student_interface:courses")
    assert "Browse all courses" in body
    assert f'href="{courses_url}"' in body


@pytest.mark.django_db
def test_anonymous_dashboard_does_not_show_welcome_back(mock_site_context):
    """Anonymous home page must not show the authenticated greeting."""
    client = Client()
    response = client.get(reverse("student_interface:dashboard"))
    assert "Welcome back" not in response.content.decode()


@pytest.mark.django_db
def test_anonymous_dashboard_does_not_show_in_progress_section(mock_site_context):
    """Anonymous home page must not show the 'In Progress' courses section."""
    client = Client()
    response = client.get(reverse("student_interface:dashboard"))
    assert "In Progress" not in response.content.decode()


@pytest.mark.django_db
def test_anonymous_dashboard_does_not_show_learning_history(mock_site_context):
    """Anonymous home page must not show the 'Learning History' section."""
    client = Client()
    response = client.get(reverse("student_interface:dashboard"))
    assert "Learning History" not in response.content.decode()


@pytest.mark.django_db
def test_anonymous_dashboard_does_not_show_unenrolled_placeholder(mock_site_context):
    """Anonymous home page must not show the 'You haven't signed up' placeholder."""
    client = Client()
    response = client.get(reverse("student_interface:dashboard"))
    assert "You haven't signed up" not in response.content.decode()


@pytest.mark.django_db
def test_anonymous_dashboard_shows_login_link(mock_site_context):
    """Anonymous home page header shows a Login link."""
    client = Client()
    response = client.get(reverse("student_interface:dashboard"))
    body = response.content.decode()
    login_url = reverse("account_login")
    assert "Login" in body
    assert login_url in body


@pytest.mark.django_db
def test_anonymous_dashboard_login_link_carries_next(mock_site_context):
    """Login link on anonymous home page carries next=/ (current path)."""
    client = Client()
    dashboard_url = reverse("student_interface:dashboard")
    response = client.get(dashboard_url)
    body = response.content.decode()
    login_url = reverse("account_login")
    # The login link must carry next=<dashboard path> so post-login lands back here.
    assert f"{login_url}?next={dashboard_url}" in body


@pytest.mark.django_db
def test_anonymous_login_link_carries_deeper_path(mock_site_context):
    """Login link carries the current path, not just root.

    Exercises login_prompt.html against a deeper anonymous page than / (the
    catalogue), so a regression that hardcodes ?next=/ would be caught.
    """
    client = Client()
    courses_url = reverse("student_interface:courses")
    response = client.get(courses_url)
    body = response.content.decode()
    login_url = reverse("account_login")
    assert f"{login_url}?next={courses_url}" in body


@pytest.mark.django_db
def test_anonymous_dashboard_shows_signup_when_allowed(mock_site_context):
    """Sign up button appears when the site allows signups."""
    SiteSignupPolicyFactory(allow_signups=True)
    client = Client()
    response = client.get(reverse("student_interface:dashboard"))
    body = response.content.decode()
    assert "Sign up" in body
    assert reverse("account_signup") in body


@pytest.mark.django_db
def test_anonymous_dashboard_hides_signup_when_disallowed(mock_site_context):
    """Sign up button is hidden when the site disallows signups."""
    SiteSignupPolicyFactory(allow_signups=False)
    client = Client()
    response = client.get(reverse("student_interface:dashboard"))
    assert "Sign up" not in response.content.decode()


@pytest.mark.django_db
def test_anonymous_dashboard_does_not_call_get_dashboard_contributions(
    mock_site_context,
):
    """Anonymous GET / must NOT invoke backend.get_dashboard_contributions.

    The authenticated path still calls it; anonymous must skip it entirely.
    """
    client = Client()
    backend_path = "freedom_ls.course_applications.backends.ApplicationCourseAccessBackend.get_dashboard_contributions"
    with mock.patch(backend_path) as mock_contributions:
        client.get(reverse("student_interface:dashboard"))
        mock_contributions.assert_not_called()


@pytest.mark.django_db
def test_authenticated_dashboard_does_not_show_hero(mock_site_context):
    """Authenticated dashboard must NOT show the anonymous hero headline."""
    user = UserFactory(first_name="Ada")
    client = Client()
    client.force_login(user)
    response = client.get(reverse("student_interface:dashboard"))
    body = response.content.decode()
    assert "Welcome back" in body
    assert "Teach the way your learners need" not in body


@pytest.mark.django_db
def test_authenticated_dashboard_still_returns_200(mock_site_context):
    """Authenticated dashboard still returns 200 for the anonymous-home variant."""
    user = UserFactory(first_name="Ada")
    client = Client()
    client.force_login(user)
    response = client.get(reverse("student_interface:dashboard"))
    assert response.status_code == 200
