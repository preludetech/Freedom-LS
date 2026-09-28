"""E2E Playwright tests for the desktop #quick-view drawer.

Covers opening, the title staying blank until the frame supplies it,
re-opening a different row, toggling the same row closed and back open with
no second request, Esc, a modified click reaching the full page instead, and
the error/Retry path.
"""

from __future__ import annotations

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import Page, Route, expect

from django.contrib.sites.models import Site

from ..conftest import _make_stub


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_clicking_a_row_opens_the_drawer_with_focus_on_the_link(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    _make_stub(name="Alpha")
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    trigger = page.get_by_role("link", name="Alpha")
    trigger.click()

    expect(page.locator("#quick-view")).to_be_visible()
    expect(page.locator("[data-stub-quick-view]")).to_have_text("Alpha")
    expect(trigger).to_be_focused()
    expect(trigger).to_have_attribute("aria-expanded", "true")


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_the_title_is_blank_while_loading_and_comes_from_the_frame(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    _make_stub(name="Alpha")
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")
    held: list[Route] = []
    page.route("**/__quick-view", lambda route: held.append(route))

    page.get_by_role("link", name="Alpha").click()
    expect(page.locator("#quick-view")).to_be_visible()
    expect(page.locator("#quick-view-body")).to_have_attribute("aria-busy", "true")
    expect(page.locator("#quick-view-title")).to_have_text("")

    held[0].continue_()
    expect(page.locator("[data-stub-quick-view]")).to_have_text("Alpha")
    expect(page.locator("#quick-view-title")).to_have_text("Alpha")


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_clicking_a_second_row_repopulates_the_drawer_and_the_table_stays_clickable(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    _make_stub(name="Alpha")
    _make_stub(name="Beta")
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    page.get_by_role("link", name="Alpha").click()
    expect(page.locator("[data-stub-quick-view]")).to_have_text("Alpha")

    page.get_by_role("link", name="Beta").click()

    expect(page.locator("[data-stub-quick-view]")).to_have_text("Beta")
    expect(page.get_by_role("link", name="Alpha")).to_have_attribute(
        "aria-expanded", "false"
    )
    expect(page.get_by_role("link", name="Beta")).to_have_attribute(
        "aria-expanded", "true"
    )


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_clicking_the_same_row_closes_and_reopens_the_drawer_with_no_second_request(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    _make_stub(name="Alpha")
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")
    quick_view_requests: list[str] = []
    page.on(
        "request",
        lambda request: quick_view_requests.append(request.url)
        if "__quick-view" in request.url
        else None,
    )
    trigger = page.get_by_role("link", name="Alpha")

    trigger.click()
    expect(page.locator("#quick-view")).to_be_visible()

    trigger.click()
    expect(page.locator("#quick-view")).to_be_hidden()

    trigger.click()
    expect(page.locator("#quick-view")).to_be_visible()
    expect(page.locator("[data-stub-quick-view]")).to_have_text("Alpha")
    assert len(quick_view_requests) == 1


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_escape_closes_the_drawer_and_returns_focus_to_the_trigger(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    _make_stub(name="Alpha")
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")
    trigger = page.get_by_role("link", name="Alpha")
    trigger.click()
    expect(page.locator("#quick-view")).to_be_visible()

    page.keyboard.press("Escape")

    expect(page.locator("#quick-view")).to_be_hidden()
    expect(trigger).to_be_focused()


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_a_ctrl_click_opens_the_full_page_in_a_new_tab(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    stub = _make_stub(name="Alpha")
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    with page.context.expect_page() as new_page_info:
        page.get_by_role("link", name="Alpha").click(modifiers=["Control"])
    new_page = new_page_info.value
    new_page.wait_for_load_state()

    expect(new_page).to_have_url(
        f"{live_server.url}/test-panel/framework/stubs/{stub.pk}"
    )
    expect(page.locator("#quick-view")).to_be_hidden()


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_a_server_error_shows_retry_and_retry_loads_the_content(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    _make_stub(name="Alpha")
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")
    attempts = {"count": 0}

    def _fail_once(route: Route) -> None:
        attempts["count"] += 1
        if attempts["count"] == 1:
            route.fulfill(status=500, body="boom")
        else:
            route.continue_()

    page.route("**/__quick-view", _fail_once)

    page.get_by_role("link", name="Alpha").click()

    expect(page.get_by_text("Something went wrong loading this.")).to_be_visible()

    page.get_by_role("button", name="Retry").click()

    expect(page.locator("[data-stub-quick-view]")).to_have_text("Alpha")
