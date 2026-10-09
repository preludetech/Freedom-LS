"""Browser flow for a staff member using the referral admin.

Writing to the clipboard needs a real browser with the Clipboard API, and
whether a long unbroken value (``key_hash``, ``raw_query``, ``user_agent``,
ad-network cookies) wraps or pushes the page past the viewport is a layout
fact only a real browser settles, so both live in Playwright.
"""

from __future__ import annotations

import pytest
from allauth.account.models import EmailAddress
from playwright.sync_api import Page, expect

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.referral_tracking.codes import absolute_code_url
from freedom_ls.referral_tracking.factories import (
    FirstTouchCountFactory,
    ReferralCodeFactory,
    SignupAttributionFactory,
)
from freedom_ls.referral_tracking.models import Door, ReferralCode
from freedom_ls.tests.playwright_fixtures import _LOGGED_IN_PASSWORD, _login_via_ui
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

COPY_BUTTONS = ("Copy /go/ URL", "Copy /d/ URL")
LONG_RAW_QUERY = "utm_source=facebook&fbclid=" + "x" * 100


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


def _code_change_url(live_server, code: ReferralCode) -> str:
    path = reverse(
        "admin:freedom_ls_referral_tracking_referralcode_change", args=[code.pk]
    )
    return f"{live_server.url}{path}"


def test_referral_admin_flow(
    live_server, page: Page, admin_user: User, referral_code: ReferralCode
) -> None:
    attribution = SignupAttributionFactory(raw_query=LONG_RAW_QUERY)
    first_touch = FirstTouchCountFactory()
    detail_pages = [
        (
            reverse(
                "admin:freedom_ls_referral_tracking_signupattribution_change",
                args=[attribution.pk],
            ),
            attribution.raw_query,
        ),
        (
            reverse(
                "admin:freedom_ls_referral_tracking_firsttouchcount_change",
                args=[first_touch.pk],
            ),
            first_touch.key_hash,
        ),
    ]
    # Grant clipboard access before any navigation happens.
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    _login_via_ui(page, live_server, str(admin_user.email), _LOGGED_IN_PASSWORD)
    page.goto(_code_change_url(live_server, referral_code))

    # The copy button puts the go URL on the clipboard. live_server_site has
    # already rewritten the site's domain to the live server's, so this is the
    # same URL the button copies.
    page.get_by_role("button", name="Copy /go/ URL").click()
    expect(page.get_by_text("Copied")).to_be_visible()
    assert page.evaluate("navigator.clipboard.readText()") == absolute_code_url(
        referral_code, Door.GO
    )

    for name in COPY_BUTTONS:
        box = page.get_by_role("button", name=name).bounding_box()
        assert box is not None
        # WCAG 2.5.8 Target Size (Minimum).
        assert box["width"] >= 24
        assert box["height"] >= 24
        # Bordered, so it does not read as body text.
        border_width = page.get_by_role("button", name=name).evaluate(
            "el => getComputedStyle(el).borderTopWidth"
        )
        assert border_width != "0px"

    # The read-only detail pages wrap long values at every width.
    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        for path, long_value in detail_pages:
            page.goto(f"{live_server.url}{path}")
            expect(page.get_by_text(long_value, exact=True)).to_be_visible()
            assert_no_horizontal_overflow(page)


def test_copy_button_reports_a_refused_clipboard(
    live_server, page: Page, admin_user: User, referral_code: ReferralCode
) -> None:
    """A rejected write must not leave the button looking like it worked."""
    _login_via_ui(page, live_server, str(admin_user.email), _LOGGED_IN_PASSWORD)
    page.goto(_code_change_url(live_server, referral_code))
    page.evaluate(
        "Object.defineProperty(navigator.clipboard, 'writeText', "
        "{value: () => Promise.reject(new Error('denied'))})"
    )

    page.get_by_role("button", name="Copy /go/ URL").click()

    expect(page.get_by_text("Could not copy")).to_be_visible()
