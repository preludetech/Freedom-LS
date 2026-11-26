"""The force delete confirmation page's disclosure rows.

Unfold's stylesheet is prebuilt and ships no ``group-open:rotate-180`` utility, so
the chevron on an opened row used to stay pointing down. Computed style is only
available in a real browser.
"""

from __future__ import annotations

import pytest
from allauth.account.models import EmailAddress
from playwright.sync_api import Page, expect
from pytest_django.live_server_helper import LiveServer

from django.contrib.sites.models import Site
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.tests.playwright_fixtures import sign_in

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_CHEVRON_TRANSFORM_JS = """
(row) => getComputedStyle(row.querySelector("summary svg")).transform
"""


@pytest.fixture
def admin_user(db: None, live_server_site: Site, mock_site_context: Site) -> User:
    """A fresh, email-verified superuser."""
    user: User = UserFactory(superuser=True)
    EmailAddress.objects.get_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )
    return user


def test_opening_a_row_turns_its_chevron_up(
    live_server: LiveServer, page: Page, admin_user: User
) -> None:
    """The chevron of an opened row used to keep its closed, downward-pointing look."""
    sign_in(page, live_server, admin_user)
    target = UserFactory()

    page.goto(
        f"{live_server.url}{reverse('admin:freedom_ls_accounts_user_force_delete')}"
        f"?ids={target.pk}"
    )

    row = page.locator("#what-will-be-deleted details").first
    expect(row).to_be_visible()
    assert row.evaluate(_CHEVRON_TRANSFORM_JS) == "none"

    row.locator("summary").click()

    expect(row).to_have_attribute("open", "")
    assert row.evaluate(_CHEVRON_TRANSFORM_JS) != "none"
