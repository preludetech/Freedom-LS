"""Browser tests for signing in: the login form, and a page that needs a session."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect
from pytest_django.live_server_helper import LiveServer

from freedom_ls.accounts.models import User
from freedom_ls.conftest import reverse_url
from freedom_ls.tests.playwright_fixtures import _LOGGED_IN_PASSWORD, _login_via_ui

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def test_an_email_verified_user_signs_in_through_the_login_form(
    page: Page, live_server: LiveServer, logged_in_user: User
) -> None:
    """The login form takes an email-verified user's email and password and lets them in."""
    _login_via_ui(page, live_server, str(logged_in_user.email), _LOGGED_IN_PASSWORD)


def test_a_signed_in_page_opens_a_page_that_needs_sign_in(
    logged_in_page: Page, live_server: LiveServer
) -> None:
    """A page behind login opens directly, with no detour through the login form."""
    # The account area opens on Personal details for a signed-in user; an anonymous
    # visitor is sent to the login form instead.
    profile_url = reverse_url(live_server, "accounts:account_profile")
    personal_details_url = reverse_url(
        live_server,
        "accounts:account_profile",
        kwargs={"path_string": "personal-details"},
    )
    logged_in_page.goto(profile_url)
    expect(logged_in_page).to_have_url(personal_details_url)
