"""The mobile navigation toggle on the page heading's row.

Whether two elements share a row is layout, and whether the toggle still
reaches the shell's sidePanel controller after an HTMX swap is Alpine
behaviour. Only a real browser shows either.
"""

from __future__ import annotations

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import Locator, Page, expect

from django.contrib.sites.models import Site

from ..helpers import make_stub

pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_MOBILE_VIEWPORT = {"width": 375, "height": 750}


def _vertical_span(locator: Locator) -> tuple[float, float]:
    box = locator.bounding_box()
    assert box is not None
    return box["y"], box["y"] + box["height"]


def _share_a_row(first: Locator, second: Locator) -> bool:
    first_top, first_bottom = _vertical_span(first)
    second_top, second_bottom = _vertical_span(second)
    return first_top < second_bottom and second_top < first_bottom


def test_toggle_shares_the_heading_row_and_survives_navigation(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    """On mobile the toggle used to take a row of its own above the heading."""
    stub = make_stub(name="row-01")
    page.set_viewport_size(_MOBILE_VIEWPORT)

    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    toggle = page.get_by_role("button", name="Open navigation panel")
    expect(toggle).to_have_count(1)
    assert _share_a_row(toggle, page.locator("#main-content h1"))

    # The toggle lives in the swapped content, so it has to keep working
    # after an HTMX navigation replaces it.
    page.locator(f"#main-content a[href$='/stubs/{stub.pk}']:visible").first.click()
    expect(page.locator("#instance-title")).to_have_text("row-01")
    page.get_by_role("button", name="Open navigation panel").click()
    expect(page.locator("dialog[aria-label='Navigation']")).to_be_visible()
