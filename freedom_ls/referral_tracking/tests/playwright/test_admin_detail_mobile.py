"""The read-only admin detail pages on a phone.

``key_hash`` is always a 64-character hex string and ``raw_query``, ``user_agent``
and the ad-network cookies routinely hold long unbroken strings. Whether such a
value wraps or pushes the page past the viewport is a layout fact only a real
browser can settle, so this lives in Playwright rather than the Django client.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from allauth.account.models import EmailAddress
from playwright.sync_api import Page, expect

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.referral_tracking.factories import (
    FirstTouchCountFactory,
    SignupAttributionFactory,
)
from freedom_ls.referral_tracking.models import FirstTouchCount, SignupAttribution
from freedom_ls.tests.playwright_fixtures import _LOGGED_IN_PASSWORD, _login_via_ui

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_PHONE_VIEWPORT = {"width": 375, "height": 812}

_LONG_RAW_QUERY = "utm_source=facebook&fbclid=" + "x" * 100


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
def phone_admin_page(page: Page, live_server, admin_user: User) -> Page:
    """A Playwright Page at a phone viewport, logged in as admin_user."""
    page.set_viewport_size(_PHONE_VIEWPORT)
    _login_via_ui(page, live_server, str(admin_user.email), _LOGGED_IN_PASSWORD)
    return page


def _signup_attribution() -> tuple[SignupAttribution, str]:
    row: SignupAttribution = SignupAttributionFactory(raw_query=_LONG_RAW_QUERY)
    return row, row.raw_query


def _first_touch_count() -> tuple[FirstTouchCount, str]:
    row: FirstTouchCount = FirstTouchCountFactory()
    return row, row.key_hash


@pytest.mark.parametrize(
    ("make_row", "change_url_name"),
    [
        (
            _signup_attribution,
            "admin:freedom_ls_referral_tracking_signupattribution_change",
        ),
        (
            _first_touch_count,
            "admin:freedom_ls_referral_tracking_firsttouchcount_change",
        ),
    ],
    ids=["signup_attribution", "first_touch_count"],
)
def test_detail_page_wraps_long_values_instead_of_scrolling_sideways(
    live_server,
    phone_admin_page: Page,
    make_row: Callable[[], tuple[SignupAttribution | FirstTouchCount, str]],
    change_url_name: str,
) -> None:
    row, long_value = make_row()

    phone_admin_page.goto(f"{live_server.url}{reverse(change_url_name, args=[row.pk])}")

    expect(phone_admin_page.get_by_text(long_value, exact=True)).to_be_visible()

    overflows = phone_admin_page.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth"
    )

    assert overflows is False
