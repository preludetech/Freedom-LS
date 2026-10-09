"""The reference page in a real browser: staff-only, tap targets, no
horizontal scroll at mobile widths.

The isolated test URLconf carries no allauth login page, so the usual
`logged_in_page` fixture cannot drive a UI login here. Instead, a `Client`
signs in server-side and its session cookie rides along into the browser
context — the smallest way to get a staff session into Playwright without a
login form to submit.
"""

from __future__ import annotations

import re

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import Page, expect

from django.conf import settings
from django.contrib.sites.models import Site
from django.test import Client

from ..helpers import make_staff_user


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_reference_page_loads_and_stays_tappable_on_mobile(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: Site,
    page: Page,
) -> None:
    staff_client = Client()
    staff_client.force_login(make_staff_user())
    session_key = staff_client.cookies[settings.SESSION_COOKIE_NAME].value
    page.context.add_cookies(
        [
            {
                "name": settings.SESSION_COOKIE_NAME,
                "value": session_key,
                "url": live_server.url,
            }
        ]
    )

    page.goto(f"{live_server.url}/test-panel/components/")

    # A rejected cookie would land on the admin login instead — fail loudly
    # rather than passing every later assertion against the wrong page.
    assert "/test-panel/components/" in page.url
    assert "/admin/login" not in page.url

    # `> h2` excludes the card examples' own titles, which are h2s too
    # (panel-card's default heading_level) but are nested inside a card
    # example, not one of the reference page's own section headings.
    expect(page.locator("section > h2")).to_have_count(12)

    page.set_viewport_size({"width": 375, "height": 812})

    # Below md the row's link stretches over the whole <li> via ::after, so
    # the reason text itself is not the topmost element at its own point —
    # force skips Playwright's obscured-element check and clicks anyway,
    # which is exactly the tap-target behaviour this proves.
    first_row_reason = page.locator("#attention-list-default li").first.get_by_text(
        "4 days idle"
    )
    first_row_reason.click(force=True)
    expect(page).to_have_url(re.compile(r"#attention-row-target$"))

    heading = page.locator("#page-header-with-actions h1")
    action_link = page.locator("#page-header-with-actions").get_by_role(
        "link", name="Add learner"
    )
    heading_box = heading.bounding_box()
    action_box = action_link.bounding_box()
    assert heading_box is not None
    assert action_box is not None
    assert action_box["y"] > heading_box["y"] + heading_box["height"]

    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
