"""Tests for the anonymous home page variant.

They cover:
- Anonymous GET / returns 200 (no login redirect)
- Anonymous home renders the anonymous hero with a link to the catalogue
- Anonymous home does NOT show authenticated-only content
- Anonymous home offers login / sign-up routes (un-parameterised, no next=)
- Anonymous GET / does NOT call backend.get_dashboard_contributions
- Authenticated dashboard unchanged (hero absent for auth user)

The assertions key on template names and structural hooks rather than on the
copy itself. A downstream project is invited to shadow these templates whole,
so their wording is not FLS's to pin.
"""

from __future__ import annotations

from unittest import mock

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import SiteSignupPolicyFactory, UserFactory

ANONYMOUS_HERO_TEMPLATE = "learner_interface/partials/anonymous_hero.html"


@pytest.mark.django_db
def test_anonymous_dashboard_returns_200(mock_site_context):
    """Anonymous GET / must return 200, not a login redirect."""
    client = Client()
    response = client.get(reverse("learner_interface:dashboard"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_anonymous_dashboard_renders_the_anonymous_hero(mock_site_context):
    """Anonymous home page shows the hero in place of a personalised greeting."""
    client = Client()
    response = client.get(reverse("learner_interface:dashboard"))
    assert ANONYMOUS_HERO_TEMPLATE in [t.name for t in response.templates]


@pytest.mark.django_db
def test_anonymous_dashboard_contains_browse_all_courses_cta(mock_site_context):
    """The anonymous hero routes visitors to the course catalogue."""
    client = Client()
    response = client.get(reverse("learner_interface:dashboard"))
    courses_url = reverse("learner_interface:courses")
    assert ANONYMOUS_HERO_TEMPLATE in [t.name for t in response.templates]
    assert f'href="{courses_url}"' in response.content.decode()


@pytest.mark.django_db
def test_anonymous_dashboard_does_not_show_the_authenticated_greeting(
    mock_site_context,
):
    """Anonymous home page must not show the personalised greeting block."""
    client = Client()
    response = client.get(reverse("learner_interface:dashboard"))
    assert 'id="dashboard-greeting"' not in response.content.decode()


@pytest.mark.django_db
def test_anonymous_dashboard_does_not_show_in_progress_section(mock_site_context):
    """Anonymous home page must not show the 'In Progress' courses section."""
    client = Client()
    response = client.get(reverse("learner_interface:dashboard"))
    assert 'id="current-courses"' not in response.content.decode()


@pytest.mark.django_db
def test_anonymous_dashboard_does_not_show_learning_history(mock_site_context):
    """Anonymous home page must not show the 'Learning History' section."""
    client = Client()
    response = client.get(reverse("learner_interface:dashboard"))
    assert 'id="learning-history"' not in response.content.decode()


@pytest.mark.django_db
def test_anonymous_dashboard_does_not_show_unenrolled_placeholder(mock_site_context):
    """Anonymous home page must not show the no-registrations placeholder."""
    client = Client()
    response = client.get(reverse("learner_interface:dashboard"))
    body = response.content.decode()
    assert 'data-testid="in-progress-empty-no-registrations"' not in body


@pytest.mark.django_db
def test_anonymous_dashboard_shows_login_link(mock_site_context):
    """Anonymous home page header offers a route to the login page."""
    client = Client()
    response = client.get(reverse("learner_interface:dashboard"))
    login_url = reverse("account_login")
    assert f'href="{login_url}"' in response.content.decode()


@pytest.mark.django_db
def test_anonymous_dashboard_shows_signup_when_allowed(mock_site_context):
    """Sign up route appears when the site allows signups."""
    SiteSignupPolicyFactory(allow_signups=True)
    client = Client()
    response = client.get(reverse("learner_interface:dashboard"))
    signup_url = reverse("account_signup")
    assert f'href="{signup_url}"' in response.content.decode()


@pytest.mark.django_db
def test_anonymous_dashboard_hides_signup_when_disallowed(mock_site_context):
    """Sign up route is hidden when the site disallows signups."""
    SiteSignupPolicyFactory(allow_signups=False)
    client = Client()
    response = client.get(reverse("learner_interface:dashboard"))
    signup_url = reverse("account_signup")
    assert f'href="{signup_url}"' not in response.content.decode()


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
        client.get(reverse("learner_interface:dashboard"))
        mock_contributions.assert_not_called()


@pytest.mark.django_db
def test_authenticated_dashboard_does_not_show_hero(mock_site_context):
    """Authenticated dashboard shows the greeting, never the anonymous hero."""
    user = UserFactory(first_name="Ada")
    client = Client()
    client.force_login(user)
    response = client.get(reverse("learner_interface:dashboard"))
    assert 'id="dashboard-greeting"' in response.content.decode()
    assert ANONYMOUS_HERO_TEMPLATE not in [t.name for t in response.templates]


@pytest.mark.django_db
def test_authenticated_dashboard_still_returns_200(mock_site_context):
    """Authenticated dashboard still returns 200 for the anonymous-home variant."""
    user = UserFactory(first_name="Ada")
    client = Client()
    client.force_login(user)
    response = client.get(reverse("learner_interface:dashboard"))
    assert response.status_code == 200
