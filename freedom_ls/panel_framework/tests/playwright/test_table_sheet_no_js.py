"""E2E test for the mobile Filter & sort sheet with JavaScript off.

The sheet's form must be reachable *and visible* below md
when JavaScript is disabled, not merely present in the DOM. The shared
bottom-sheet dialog is closed by default (opacity:0, translateY(100%)), and
the sheet's own <noscript> override only reset display/position, leaving it
technically submittable but invisible.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import Browser, Page, expect

from django.contrib.sites.models import Site

from ..helpers import make_stub

_PHONE_VIEWPORT = {"width": 390, "height": 844}


@pytest.fixture
def no_js_page(browser: Browser) -> Iterator[Page]:
    """A page in a fresh browser context with JavaScript disabled, for
    proving the sheet is visible without it."""
    context = browser.new_context(java_script_enabled=False, viewport=_PHONE_VIEWPORT)
    page = context.new_page()
    yield page
    context.close()


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_sheet_visible_on_phone_with_js_off(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    no_js_page: Page,
) -> None:
    [make_stub(name=f"row-{i:02d}") for i in range(3)]
    page = no_js_page

    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    sheet = page.locator("#stubs-sheet")
    expect(sheet).to_be_visible()
    expect(sheet).to_have_css("opacity", "1")
    expect(sheet).to_have_css("transform", "none")
