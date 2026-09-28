"""E2E Playwright tests for the #quick-view drawer below the md breakpoint.

Covers the mobile sheet's modal presentation, Back dismissing it without
touching the URL, and surviving a resize across the breakpoint while open.
Desktop behaviour lives in test_quick_view_htmx.py.
"""

from __future__ import annotations

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import Page, expect

from django.contrib.sites.models import Site

from ..conftest import _make_stub

# Narrow enough that the drawer opens as the modal sheet rather than the
# docked desktop column (quickView docks it from 768px up).
_MOBILE_VIEWPORT = {"width": 375, "height": 750}
_DESKTOP_VIEWPORT = {"width": 1024, "height": 800}


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_the_drawer_opens_as_a_modal_sheet_below_the_breakpoint(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    _make_stub(name="Alpha")
    page.set_viewport_size(_MOBILE_VIEWPORT)
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    page.get_by_role("link", name="Alpha").click()

    expect(page.locator("dialog:modal")).to_have_count(1)
    expect(page.locator("[data-stub-quick-view]")).to_have_text("Alpha")


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_back_closes_the_mobile_sheet_and_leaves_the_url_unchanged(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    _make_stub(name="Alpha")
    page.set_viewport_size(_MOBILE_VIEWPORT)
    list_url = f"{live_server.url}/test-panel/framework/stubs/"
    page.goto(list_url)

    page.get_by_role("link", name="Alpha").click()
    expect(page.locator("#quick-view")).to_be_visible()

    page.go_back()

    expect(page.locator("#quick-view")).to_be_hidden()
    expect(page).to_have_url(list_url)


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
    page.get_by_role("link", name="Alpha").click()
    expect(page.locator("dialog:modal")).to_have_count(1)

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


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_crossing_the_breakpoint_twice_while_open_still_unwinds_a_single_entry(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    stub = _make_stub(name="Alpha")
    detail_url = f"{live_server.url}/test-panel/framework/stubs/{stub.pk}"
    list_url = f"{live_server.url}/test-panel/framework/stubs/"
    page.set_viewport_size(_MOBILE_VIEWPORT)
    page.goto(detail_url)
    page.goto(list_url)

    page.get_by_role("link", name="Alpha").click()
    expect(page.locator("dialog:modal")).to_have_count(1)

    # Cross to desktop and back to mobile before closing, as in the bug
    # report: neither resize should leave a dead history entry behind.
    page.set_viewport_size(_DESKTOP_VIEWPORT)
    expect(page.locator("dialog:modal")).to_have_count(0)
    expect(page.locator("#quick-view")).to_be_visible()

    page.set_viewport_size(_MOBILE_VIEWPORT)
    expect(page.locator("dialog:modal")).to_have_count(1)

    page.get_by_role("button", name="Close").click()
    expect(page.locator("#quick-view")).to_be_hidden()
    expect(page).to_have_url(list_url)

    # The sheet owned at most one history entry and Close already unwound
    # it, so a single further Back should leave the list page entirely.
    page.go_back()

    expect(page).to_have_url(detail_url)
