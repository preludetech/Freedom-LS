"""Browser flow for the ``#quick-view`` drawer on the stub list.

The stub views have no authentication, so the flow needs no login. Cases that
intercept the quick-view request are separate functions.
"""

from __future__ import annotations

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import Locator, Page, Request, Route, ViewportSize, expect

from django.contrib.sites.models import Site

from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

from ..helpers import make_stub

pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_FRAMEWORK_PATH = "/test-panel/framework"
_LIST_PATH = f"{_FRAMEWORK_PATH}/stubs/"
_ERROR_TEXT = "Something went wrong loading this."
# Viewports narrower than this width get the bottom sheet.
_PHONE_MAX_WIDTH = 768
# The drawer docks beside the page from this width up.
_DOCKED_MIN_WIDTH = 1280
_DRAWER_WIDTH = 480
_CROSSING_VIEWPORT: ViewportSize = {"width": 1280, "height": 800}


def _trigger(page: Page, name: str) -> Locator:
    return page.get_by_role("link", name=f"Quick view: {name}")


def _record_quick_view_requests(page: Page) -> list[str]:
    """Collect the URL of every quick-view request the page makes from now on."""
    urls: list[str] = []

    def _record(request: Request) -> None:
        if "__quick-view" in request.url:
            urls.append(request.url)

    page.on("request", _record)
    return urls


def _fail_first_quick_view(page: Page) -> dict[str, int]:
    """Answer the first quick-view request with a 500, then let the rest through."""
    attempts = {"count": 0}

    def _fail_once(route: Route) -> None:
        attempts["count"] += 1
        if attempts["count"] == 1:
            route.fulfill(status=500, body="boom")
        else:
            route.continue_()

    page.route("**/__quick-view", _fail_once)
    return attempts


def test_quick_view_drawer(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    alpha = make_stub(name="Alpha")
    make_stub(name="Beta")
    detail_stub = make_stub(name="History Target")
    for i in range(9):
        make_stub(name=f"row-{i:02d}")
    list_url = f"{live_server.url}{_LIST_PATH}"
    # The sidebar's own reverse()d link has no trailing slash.
    sidebar_list_url = f"{live_server.url}{_FRAMEWORK_PATH}/stubs"
    detail_url = f"{live_server.url}{_FRAMEWORK_PATH}/stubs/{detail_stub.pk}"
    quick_view = page.locator("#quick-view")
    content = page.locator("[data-stub-quick-view]")
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))

    page.set_viewport_size(QA_VIEWPORTS[2])
    page.goto(list_url)

    # The title is blank while the frame loads and comes from the frame.
    held: list[Route] = []
    page.route("**/__quick-view", lambda route: held.append(route))
    alpha_trigger = _trigger(page, "Alpha")
    alpha_trigger.click()
    expect(quick_view).to_be_visible()
    expect(page.locator("#quick-view-body")).to_have_attribute("aria-busy", "true")
    expect(page.locator("#quick-view-title")).to_have_text("")
    held[0].continue_()
    page.unroute("**/__quick-view")
    expect(content).to_have_text("Alpha")
    expect(page.locator("#quick-view-title")).to_have_text("Alpha")
    expect(alpha_trigger).to_be_focused()
    expect(alpha_trigger).to_have_attribute("aria-expanded", "true")

    # A second row repopulates the drawer while the table stays clickable.
    beta_trigger = _trigger(page, "Beta")
    beta_trigger.click()
    expect(content).to_have_text("Beta")
    expect(alpha_trigger).to_have_attribute("aria-expanded", "false")
    expect(beta_trigger).to_have_attribute("aria-expanded", "true")

    # The same row closes and reopens with no second request.
    requests = _record_quick_view_requests(page)
    beta_trigger.click()
    expect(quick_view).to_be_hidden()
    beta_trigger.click()
    expect(quick_view).to_be_visible()
    expect(content).to_have_text("Beta")
    assert requests == []

    # Esc closes the drawer and returns focus to the trigger.
    page.keyboard.press("Escape")
    expect(quick_view).to_be_hidden()
    expect(beta_trigger).to_be_focused()

    # A ctrl-click opens the full page in a new tab and leaves the drawer shut.
    with page.context.expect_page() as new_page_info:
        alpha_trigger.click(modifiers=["Control"])
    new_page = new_page_info.value
    new_page.wait_for_load_state()
    expect(new_page).to_have_url(f"{live_server.url}{_FRAMEWORK_PATH}/stubs/{alpha.pk}")
    expect(quick_view).to_be_hidden()
    new_page.close()

    # An open modal dialog is gone after navigating away and back.
    page.goto(list_url)
    page.get_by_role("button", name="Create Item").click()
    expect(page.locator("#app-modal")).to_be_visible()
    page.evaluate(
        f"htmx.ajax('GET', '{_FRAMEWORK_PATH}/stubs/{detail_stub.pk}', "
        f"{{target: '#main-content', swap: 'outerHTML', "
        f"push: '{_FRAMEWORK_PATH}/stubs/{detail_stub.pk}'}})"
    )
    expect(page).to_have_url(detail_url)
    page.go_back()
    expect(page).to_have_url(list_url)
    expect(page.locator("#app-modal")).to_be_hidden()

    # An open drawer is gone after navigating away and back, and reopening it
    # refetches. Starting from the detail page makes the sidebar's "Stubs"
    # link lead somewhere different, so htmx pushes an entry for Back to undo.
    page.goto(detail_url)
    history_trigger = _trigger(page, "History Target")
    history_trigger.click()
    expect(quick_view).to_be_visible()
    expect(content).to_have_text("History Target")
    page.get_by_label("Sections").get_by_role("link", name="Stubs", exact=True).click()
    expect(page).to_have_url(sidebar_list_url)
    page.go_back()
    expect(page).to_have_url(detail_url)
    expect(quick_view).to_be_hidden()

    requests = _record_quick_view_requests(page)
    history_trigger.click()
    expect(quick_view).to_be_visible()
    expect(page.locator("#quick-view-title")).to_have_text("History Target")
    expect(content).to_have_text("History Target")
    expect(history_trigger).to_have_attribute("aria-expanded", "true")
    assert len(requests) == 1

    # A history-restore swap carries no detail.target; the event is dispatched
    # directly because whether a live listener sees it depends on when Alpine
    # tears the old page down.
    page.goto(list_url)
    expect(page.locator("#app-modal")).to_be_attached()
    page.evaluate(
        "document.body.dispatchEvent(new CustomEvent('htmx:afterSwap', "
        "{bubbles: true, detail: {elt: document.body}}))"
    )
    assert page_errors == []

    # Layout at each viewport.
    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(list_url)
        assert_no_horizontal_overflow(page)
        width = viewport["width"]
        height = viewport["height"]
        is_phone = width < _PHONE_MAX_WIDTH
        is_docked = width >= _DOCKED_MIN_WIDTH

        _trigger(page, "Alpha").click()
        expect(content).to_have_text("Alpha")
        # The slide-in transform transitions over 200ms; measuring before it
        # ends would race the animation.
        expect(quick_view).to_have_css("transform", "none")

        # The drawer is not modal, so the rest of the page stays usable.
        expect(page.locator("dialog:modal")).to_have_count(0)
        assert page.evaluate("getComputedStyle(document.documentElement).overflow") != (
            "hidden"
        )
        box = quick_view.bounding_box()
        assert box is not None

        if is_phone:
            assert box["x"] == pytest.approx(0, abs=1)
            assert box["width"] == pytest.approx(width, abs=1)
            assert box["y"] + box["height"] == pytest.approx(height, abs=1)
            # Half the screen at most, so the page above stays in view.
            assert box["height"] <= height / 2 + 1
            expect(quick_view).to_have_css("border-top-left-radius", "16px")
            expect(quick_view).to_have_css("border-top-right-radius", "16px")
            expect(quick_view).to_have_css("border-top-width", "1px")
            expect(quick_view).to_have_css("border-bottom-width", "0px")
        else:
            assert box["x"] + box["width"] == pytest.approx(width, abs=1)
            assert box["width"] == pytest.approx(_DRAWER_WIDTH, abs=2)
            expect(quick_view).to_have_css("border-top-left-radius", "0px")
            if is_docked:
                assert box["y"] == pytest.approx(0, abs=1)
                assert box["height"] == pytest.approx(height, abs=1)
                # The page content makes room for the docked drawer.
                table_box = page.locator("#main-content table").bounding_box()
                create_box = page.get_by_role(
                    "button", name="Create Item"
                ).bounding_box()
                assert table_box is not None
                assert create_box is not None
                assert table_box["x"] + table_box["width"] <= box["x"]
                assert create_box["x"] + create_box["width"] <= box["x"]
            else:
                # Too narrow to dock but wide enough for a side drawer, laid
                # over the page below the site header. --sidebar-top is the
                # header's height, set by sidePanel.
                header_bottom = page.evaluate(
                    "parseFloat(getComputedStyle(document.querySelector("
                    "'#quick-view')).getPropertyValue('--sidebar-top')) || 0"
                )
                assert box["y"] == pytest.approx(header_bottom, abs=1)
                assert box["y"] + box["height"] == pytest.approx(height, abs=1)

        # Another row can be previewed straight away. A tablet drawer covers
        # the table's one column, so the keyboard reaches that trigger.
        beta_trigger = _trigger(page, "Beta")
        if is_phone:
            beta_trigger.click()
        else:
            beta_trigger.focus()
            page.keyboard.press("Enter")
        expect(content).to_have_text("Beta")

        if is_phone:
            # The page scrolls its last row clear of the sheet.
            page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
            row_box = _trigger(page, "row-06").bounding_box()
            sheet_box = quick_view.bounding_box()
            assert row_box is not None
            assert sheet_box is not None
            assert row_box["y"] + row_box["height"] <= sheet_box["y"]

        # The drawer is not displayed under print media.
        page.emulate_media(media="print")
        assert quick_view.evaluate("el => getComputedStyle(el).display") == "none"
        page.emulate_media(media="screen")

        page.keyboard.press("Escape")
        expect(quick_view).to_be_hidden()
        expect(beta_trigger).to_be_focused()

    # Crossing the docking breakpoint while open keeps the content with no
    # new request.
    page.set_viewport_size(QA_VIEWPORTS[0])
    page.goto(list_url)
    _trigger(page, "Alpha").click()
    expect(content).to_have_text("Alpha")
    requests = _record_quick_view_requests(page)

    page.set_viewport_size(_CROSSING_VIEWPORT)

    expect(quick_view).to_be_visible()
    expect(page.locator("dialog:modal")).to_have_count(0)
    expect(content).to_have_text("Alpha")
    assert requests == []


def test_server_error_shows_retry_and_retry_loads(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    make_stub(name="Alpha")
    page.goto(f"{live_server.url}{_LIST_PATH}")
    _fail_first_quick_view(page)

    _trigger(page, "Alpha").click()
    expect(page.get_by_text(_ERROR_TEXT)).to_be_visible()

    page.get_by_role("button", name="Retry").click()
    expect(page.locator("[data-stub-quick-view]")).to_have_text("Alpha")


def test_back_to_a_shown_row_after_another_failed_loads_it_again(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    make_stub(name="Alpha")
    beta = make_stub(name="Beta")
    page.goto(f"{live_server.url}{_LIST_PATH}")
    page.route(
        f"**/{beta.pk}/__quick-view",
        lambda route: route.fulfill(status=500, body="boom"),
    )

    _trigger(page, "Alpha").click()
    expect(page.locator("[data-stub-quick-view]")).to_have_text("Alpha")
    _trigger(page, "Beta").click()
    expect(page.get_by_text(_ERROR_TEXT)).to_be_visible()

    _trigger(page, "Alpha").click()
    expect(page.locator("#quick-view")).to_be_visible()
    expect(page.locator("[data-stub-quick-view]")).to_have_text("Alpha")


def test_reopening_a_row_after_closing_mid_load_shows_the_reopened_row(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    make_stub(name="Alpha")
    beta = make_stub(name="Beta")
    page.goto(f"{live_server.url}{_LIST_PATH}")
    held: list[Route] = []
    page.route(f"**/{beta.pk}/__quick-view", lambda route: held.append(route))

    _trigger(page, "Alpha").click()
    expect(page.locator("[data-stub-quick-view]")).to_have_text("Alpha")
    _trigger(page, "Beta").click()
    expect(page.locator("#quick-view-body")).to_have_attribute("aria-busy", "true")
    page.keyboard.press("Escape")
    expect(page.locator("#quick-view")).to_be_hidden()

    _trigger(page, "Alpha").click()
    expect(page.locator("[data-stub-quick-view]")).to_have_text("Alpha")
    expect(_trigger(page, "Alpha")).to_have_attribute("aria-expanded", "true")


def test_reopening_a_row_whose_load_failed_requests_it_again(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    make_stub(name="Alpha")
    page.goto(f"{live_server.url}{_LIST_PATH}")
    attempts = _fail_first_quick_view(page)
    trigger = _trigger(page, "Alpha")

    trigger.click()
    expect(page.get_by_text(_ERROR_TEXT)).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator("#quick-view")).to_be_hidden()

    trigger.click()
    expect(page.locator("[data-stub-quick-view]")).to_have_text("Alpha")
    assert attempts["count"] == 2
