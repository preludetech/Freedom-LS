"""E2E Playwright tests for the #quick-view drawer below the docked breakpoint.

The quick view never takes the page over: below 1280px it is a side drawer
or a phone sheet laid over the page, not a modal, so the rest of the page
stays usable and another row can be previewed straight away. Covers that,
Escape, the room the phone sheet leaves to scroll the page clear of it, and
surviving a resize across the breakpoint while open. Desktop behaviour lives
in test_quick_view_htmx.py.
"""

from __future__ import annotations

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import Page, expect

from django.contrib.sites.models import Site

from ..conftest import _make_stub

_MOBILE_VIEWPORT = {"width": 375, "height": 750}
_TABLET_VIEWPORT = {"width": 1024, "height": 800}
_DESKTOP_VIEWPORT = {"width": 1280, "height": 800}


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "viewport", [_MOBILE_VIEWPORT, _TABLET_VIEWPORT], ids=["phone", "tablet"]
)
def test_the_open_quick_view_leaves_the_page_usable(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
    viewport: dict[str, int],
) -> None:
    _make_stub(name="Alpha")
    _make_stub(name="Beta")
    page.set_viewport_size(viewport)
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    page.get_by_role("link", name="Quick view: Alpha").click()
    expect(page.locator("[data-stub-quick-view]")).to_have_text("Alpha")

    expect(page.locator("dialog:modal")).to_have_count(0)
    assert page.evaluate("getComputedStyle(document.documentElement).overflow") != (
        "hidden"
    )

    # The stub table's one column spans the page, so on the tablet its
    # trigger sits under the drawer; a modal's inert page could not be
    # reached by keyboard either, so that route proves the same thing.
    beta = page.get_by_role("link", name="Quick view: Beta")
    if viewport == _MOBILE_VIEWPORT:
        beta.click()
    else:
        beta.focus()
        page.keyboard.press("Enter")

    expect(page.locator("[data-stub-quick-view]")).to_have_text("Beta")


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_escape_closes_the_sheet_and_returns_focus_to_the_trigger(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    _make_stub(name="Alpha")
    page.set_viewport_size(_MOBILE_VIEWPORT)
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")
    trigger = page.get_by_role("link", name="Quick view: Alpha")
    trigger.click()
    expect(page.locator("[data-stub-quick-view]")).to_have_text("Alpha")

    page.keyboard.press("Escape")

    expect(page.locator("#quick-view")).to_be_hidden()
    expect(trigger).to_be_focused()


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_the_page_can_scroll_its_last_row_clear_of_the_phone_sheet(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    for i in range(10):
        _make_stub(name=f"row-{i:02d}")
    page.set_viewport_size(_MOBILE_VIEWPORT)
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")
    page.get_by_role("link", name="Quick view: row-00").click()
    sheet = page.locator("#quick-view")
    expect(sheet).to_have_css("transform", "none")

    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")

    last_row = page.get_by_role("link", name="Quick view: row-09")
    row_box = last_row.bounding_box()
    sheet_box = sheet.bounding_box()
    assert row_box is not None
    assert sheet_box is not None
    assert row_box["y"] + row_box["height"] <= sheet_box["y"]


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_crossing_the_breakpoint_while_open_keeps_the_content_with_no_new_request(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    _make_stub(name="Alpha")
    page.set_viewport_size(_MOBILE_VIEWPORT)
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")
    page.get_by_role("link", name="Quick view: Alpha").click()
    expect(page.locator("[data-stub-quick-view]")).to_have_text("Alpha")

    quick_view_requests: list[str] = []
    page.on(
        "request",
        lambda request: (
            quick_view_requests.append(request.url)
            if "__quick-view" in request.url
            else None
        ),
    )

    page.set_viewport_size(_DESKTOP_VIEWPORT)

    expect(page.locator("#quick-view")).to_be_visible()
    expect(page.locator("dialog:modal")).to_have_count(0)
    expect(page.locator("[data-stub-quick-view]")).to_have_text("Alpha")
    assert quick_view_requests == []
