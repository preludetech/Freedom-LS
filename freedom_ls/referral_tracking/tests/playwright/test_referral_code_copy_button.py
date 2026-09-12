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


@pytest.fixture
def referral_code(admin_user: User) -> ReferralCode:
    """A saved code, so the change form renders URLs rather than the unsaved message."""
    code: ReferralCode = ReferralCodeFactory()
    return code


@pytest.fixture
def change_form(
    page: Page, live_server, admin_user: User, referral_code: ReferralCode
) -> Page:
    """A Playwright Page sitting on referral_code's change form, logged in as admin."""
    # Grant clipboard access before any navigation happens.
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    _login_via_ui(page, live_server, str(admin_user.email), _LOGGED_IN_PASSWORD)
    change_url = reverse(
        "admin:freedom_ls_referral_tracking_referralcode_change",
        args=[referral_code.pk],
    )
    page.goto(f"{live_server.url}{change_url}")
    return page


def test_copy_button_puts_the_go_url_on_the_clipboard(
    change_form: Page, referral_code: ReferralCode
) -> None:
    # live_server_site (pulled in via admin_user) has already rewritten the
    # site's domain to the live server's, so this reads the same URL the
    # button will copy.
    expected_url = absolute_code_url(referral_code, Door.GO)

    change_form.get_by_role("button", name="Copy /go/ URL").click()

    expect(change_form.get_by_text("Copied")).to_be_visible()
    assert change_form.evaluate("navigator.clipboard.readText()") == expected_url


@pytest.mark.parametrize("name", ["Copy /go/ URL", "Copy /d/ URL"])
def test_copy_button_meets_the_minimum_target_size(
    change_form: Page, name: str
) -> None:
    box = change_form.get_by_role("button", name=name).bounding_box()

    assert box is not None
    # WCAG 2.5.8 Target Size (Minimum).
    assert box["width"] >= 24
    assert box["height"] >= 24


@pytest.mark.parametrize("name", ["Copy /go/ URL", "Copy /d/ URL"])
def test_copy_button_is_bordered_so_it_does_not_read_as_body_text(
    change_form: Page, name: str
) -> None:
    button = change_form.get_by_role("button", name=name)

    border_width = button.evaluate("el => getComputedStyle(el).borderTopWidth")

    assert border_width != "0px"
