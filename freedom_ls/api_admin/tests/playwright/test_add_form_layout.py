"""The API key add form in the admin at phone and tablet widths."""

from __future__ import annotations

import pytest
from allauth.account.models import EmailAddress
from playwright.sync_api import Page

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.tests.playwright_fixtures import _LOGGED_IN_PASSWORD, _login_via_ui
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


@pytest.fixture
def admin_user(db, live_server_site, mock_site_context) -> User:
    """A fresh, email-verified superuser."""
    user: User = UserFactory(superuser=True, password=_LOGGED_IN_PASSWORD)
    EmailAddress.objects.get_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )
    return user


def test_add_form_fits_the_viewport_with_long_scope_labels(
    live_server, page: Page, admin_user: User
) -> None:
    """The long scope labels did not wrap, so the add form scrolled sideways."""
    _login_via_ui(page, live_server, str(admin_user.email), _LOGGED_IN_PASSWORD)

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(f"{live_server.url}{reverse('admin:freedom_ls_api_apikey_add')}")
        assert_no_horizontal_overflow(page)
