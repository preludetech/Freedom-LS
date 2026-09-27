"""Shared Playwright fixtures for educator_interface browser tests."""

from __future__ import annotations

import pytest
import pytest_django.live_server_helper
from allauth.account.models import EmailAddress
from playwright.sync_api import Page

from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.tests.playwright_fixtures import _LOGGED_IN_PASSWORD, _login_via_ui


@pytest.fixture
def educator_user(db, live_server_site: Site, mock_site_context: Site) -> User:
    """A fresh, email-verified staff user.

    A staff variant of freedom_ls.tests.playwright_fixtures.logged_in_user —
    that fixture is hard-coded to a plain learner.
    """
    user: User = UserFactory(staff=True, password=_LOGGED_IN_PASSWORD)
    EmailAddress.objects.get_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )
    return user


@pytest.fixture
def educator_logged_in_page(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    educator_user: User,
) -> Page:
    """A Playwright Page logged in as educator_user."""
    _login_via_ui(page, live_server, str(educator_user.email), _LOGGED_IN_PASSWORD)
    return page
