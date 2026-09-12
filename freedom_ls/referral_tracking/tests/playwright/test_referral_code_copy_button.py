"""The copy button on a `ReferralCode` change page.

Writing to the clipboard needs a real browser with the Clipboard API, which
the Django test client cannot exercise, so this lives in Playwright.
"""

from __future__ import annotations

import pytest
from allauth.account.models import EmailAddress
from playwright.sync_api import Page, expect

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.referral_tracking.codes import absolute_code_url
from freedom_ls.referral_tracking.factories import ReferralCodeFactory
from freedom_ls.referral_tracking.models import Door, ReferralCode
from freedom_ls.tests.playwright_fixtures import _LOGGED_IN_PASSWORD, _login_via_ui

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


def test_copy_button_puts_the_go_url_on_the_clipboard(
    page: Page, live_server, admin_user: User
) -> None:
    # Grant clipboard access before any navigation happens.
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])

    # live_server_site (pulled in via admin_user) has already rewritten the
    # site's domain to the live server's, so this reads the same URL the
    # button will copy.
    referral_code: ReferralCode = ReferralCodeFactory()
    expected_url = absolute_code_url(referral_code, Door.GO)

    _login_via_ui(page, live_server, str(admin_user.email), _LOGGED_IN_PASSWORD)
    change_url = reverse(
        "admin:freedom_ls_referral_tracking_referralcode_change",
        args=[referral_code.pk],
    )
    page.goto(f"{live_server.url}{change_url}")

    page.get_by_role("button", name="Copy /go/ URL").click()

    expect(page.get_by_text("Copied")).to_be_visible()
    assert page.evaluate("navigator.clipboard.readText()") == expected_url
