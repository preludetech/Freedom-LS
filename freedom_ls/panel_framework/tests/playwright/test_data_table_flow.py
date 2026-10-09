"""Browser flow for the stub data table: sorting, paging, search, selection,
bulk actions, tabs and the phone layout.

The stub list view has no authentication, so the flow needs no login.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import Browser, Locator, Page, ViewportSize, expect

from django.contrib.sites.models import Site

from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

from ..helpers import make_stub
from ..stub_models import StubModel
from ..stub_panels import StubDataTable
from .assertions import expect_no_nested_panel

pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_FRAMEWORK_PATH = "/test-panel/framework"
_LIST_PATH = f"{_FRAMEWORK_PATH}/stubs/"
PAGE_SIZE = StubDataTable.page_size
# Below Tailwind's `md` breakpoint the table is replaced by a card list.
_PHONE_MAX_WIDTH = 768
_PHONE_VIEWPORT: ViewportSize = {"width": 390, "height": 844}


def _expect_swap_settled(page: Page) -> None:
    """htmx attaches triggers to swapped-in content only once it settles."""
    expect(page.locator(".htmx-added")).to_have_count(0)


def _page_link(page: Page, number: int) -> Locator:
    """The pagination link for page ``number`` (exact: row links also hold digits)."""
    return page.get_by_role("link", name=str(number), exact=True).first


@contextmanager
def _no_js_page(
    browser: Browser, viewport: ViewportSize | None = None
) -> Iterator[Page]:
    """A page in a fresh browser context with JavaScript disabled."""
    context = browser.new_context(java_script_enabled=False, viewport=viewport)
    try:
        yield context.new_page()
    finally:
        context.close()


def test_data_table_interaction(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    stubs = [make_stub(name=f"row-{i:02d}") for i in range(PAGE_SIZE + 5)]
    list_url = f"{live_server.url}{_LIST_PATH}"
    page.set_viewport_size(QA_VIEWPORTS[2])

    # Sorting and paging a panel on an instance page never nests panel frames.
    page.goto(f"{live_server.url}{_FRAMEWORK_PATH}/stubs/{stubs[0].pk}/")
    expect_no_nested_panel(page)
    # Each click waits for its pushed URL so the next one hits the swapped link.
    for sort_param in ("name", "-name", "name"):
        page.get_by_role("link", name="Name").click()
        expect(page).to_have_url(re.compile(rf"stub-sort={sort_param}$"))
        expect_no_nested_panel(page)
    _page_link(page, 2).click()
    expect(page).to_have_url(re.compile(r"stub-page=2"))
    expect_no_nested_panel(page)
    _page_link(page, 1).click()
    expect(page).not_to_have_url(re.compile(r"stub-page=2"))
    expect_no_nested_panel(page)

    # Sorting the list swaps without nesting, moves focus to the table anchor
    # and leaves the filter and sort sheet closed.
    page.goto(list_url)
    expect(page.locator("[data-panel]")).to_have_count(1)
    expect_no_nested_panel(page, name="")
    sheet = page.locator("#stubs-sheet")
    expect(sheet).to_have_count(1)
    expect(sheet).not_to_have_attribute("open", re.compile(".*"))

    page.get_by_role("link", name="Name").click()
    expect(page).to_have_url(re.compile(r"stubs-sort=name"))
    expect(page.locator("#stubs-table [data-table-anchor]")).to_be_focused()
    expect(page.locator("#stubs-search input[name='stubs-sort']")).to_have_count(1)
    expect(page.locator("[data-panel]")).to_have_count(1)
    expect_no_nested_panel(page, name="")
    expect(sheet).not_to_have_attribute("open", re.compile(".*"))

    # Paging keeps the sort param and does not nest frames.
    page2_link = _page_link(page, 2)
    expect(page2_link).to_have_attribute("href", re.compile(r"stubs-sort=name"))
    expect(page2_link).to_have_attribute("href", re.compile(r"stubs-page=2"))
    page2_link.click()
    expect(page).to_have_url(re.compile(r"stubs-page=2"))
    expect(page).to_have_url(re.compile(r"stubs-sort=name"))
    expect_no_nested_panel(page, name="")

    # Back restores the sorted, unpaged table in the URL and the rows.
    page.go_back()
    expect(page).to_have_url(re.compile(r"stubs-sort=name"))
    expect(page).not_to_have_url(re.compile(r"stubs-page"))
    rows = page.locator("#stubs-table tbody tr")
    expect(rows.first).to_contain_text("row-00")

    # Search narrows the table while a sort is active.
    search = page.locator("#stubs-q")
    search.fill("row-01")
    expect(rows).to_have_count(1)
    expect(rows.first).to_contain_text("row-01")
    _expect_swap_settled(page)

    # A reader who pauses mid-search and carries on typing keeps focus and
    # every character.
    search.fill("")
    expect(rows).to_have_count(PAGE_SIZE)
    _expect_swap_settled(page)
    search.click()
    search.press_sequentially("row-0")
    expect(page).to_have_url(re.compile(r"stubs-q=row-0"))
    _expect_swap_settled(page)
    page.keyboard.type("1")
    expect(search).to_have_value("row-01")
    expect(search).to_be_focused()
    expect(rows).to_have_count(1)
    expect(rows.first).to_contain_text("row-01")

    # Paging one of two tables keeps the other's page in the URL and across a
    # reload; the first page click on a nested table pushes the tab's own URL.
    pair_url = f"{live_server.url}{_FRAMEWORK_PATH}/stubs/{stubs[0].pk}/__tabs/pair"
    page.goto(pair_url)
    page.locator("#a-table").get_by_role("link", name="2", exact=True).first.click()
    expect(page).to_have_url(re.compile(r"__tabs/pair\?a-page=2$"))
    expect(page).not_to_have_url(re.compile(r"__panels"))

    page.goto(pair_url)
    page.locator("#b-table").get_by_role("link", name="2", exact=True).click()
    expect(page).to_have_url(re.compile(r"b-page=2"))
    page.locator("#a-table").get_by_role("link", name="2", exact=True).click()
    expect(page).to_have_url(re.compile(r"a-page=2"))
    expect(page).to_have_url(re.compile(r"b-page=2"))
    page.reload()
    expect(page.locator("#a-table")).to_contain_text(f"row-{PAGE_SIZE:02d}")
    expect(page.locator("#b-table")).to_contain_text(f"row-{PAGE_SIZE:02d}")

    # The header checkbox is checked, indeterminate or clear to match the rows.
    page.goto(list_url)
    # The mobile card list has its own "select all" control with the same
    # label, so the header checkbox is scoped to the desktop table.
    header_checkbox = page.locator("#stubs-table thead").get_by_label(
        "Select all on this page"
    )
    row_checkboxes = page.locator("#stubs-table tbody input[name='keys']")
    expect(row_checkboxes).to_have_count(PAGE_SIZE)
    row_checkboxes.first.check()
    expect(header_checkbox).to_be_checked(indeterminate=True)
    for i in range(1, PAGE_SIZE):
        row_checkboxes.nth(i).check()
    expect(header_checkbox).to_be_checked()
    row_checkboxes.first.uncheck()
    header_checkbox.check()
    for i in range(PAGE_SIZE):
        expect(row_checkboxes.nth(i)).to_be_checked()

    # Sorting clears the selection.
    expect(page.get_by_text(f"{PAGE_SIZE} selected", exact=False)).to_be_visible()
    page.get_by_role("link", name="Name").click()
    expect(page.get_by_text("selected", exact=False)).to_be_hidden()
    expect(page.locator("#stubs-table tbody input[name='keys']:checked")).to_have_count(
        0
    )

    # A bulk action confirms in the shared modal; Cancel acts on nothing.
    page.goto(list_url)
    modal = page.locator("#app-modal")
    row_checkboxes.nth(0).check()
    row_checkboxes.nth(1).check()
    page.get_by_role("button", name="Mark processed").click()
    expect(modal).to_be_visible()
    expect(modal.get_by_text("This will affect 2 stub models.")).to_be_visible()
    modal.get_by_role("button", name="Cancel").click()
    expect(modal).to_be_hidden()
    assert not StubModel.objects.filter(is_active=False).exists()

    page.get_by_role("button", name="Mark processed").click()
    expect(modal).to_be_visible()
    modal.get_by_role("button", name="Mark processed").click()
    expect(page).to_have_url(f"{live_server.url}{_FRAMEWORK_PATH}/stubs")
    expect(modal).to_be_hidden()
    active_by_name = dict(StubModel.objects.values_list("name", "is_active"))
    assert active_by_name["row-00"] is False
    assert active_by_name["row-01"] is False
    assert active_by_name["row-02"] is True

    # Switching tab, then Back and Forward, keeps the URL and the tab together.
    instance_url = f"{live_server.url}{_FRAMEWORK_PATH}/stubs/{stubs[5].pk}"
    page.goto(instance_url)
    expect(page.locator("[data-panel='default']")).to_have_count(1)
    history_length = page.evaluate("history.length")

    details_link = page.get_by_role("link", name="Details", exact=True)
    details_link.click()
    expect(page).to_have_url(re.compile(r"/__tabs/details$"))
    expect(page.locator("[data-panel='details']")).to_have_count(1)
    expect(page.locator("[data-panel='default']")).to_have_count(0)
    expect_no_nested_panel(page, name="details")
    expect(details_link).to_have_attribute("aria-current", "page")
    assert page.evaluate("history.length") == history_length + 1
    assert (
        page.evaluate(
            "document.activeElement && document.activeElement.textContent.trim()"
        )
        == "Details"
    )

    page.go_back()
    expect(page).to_have_url(re.compile(rf"/stubs/{stubs[5].pk}$"))
    expect(page.locator("[data-panel='default']")).to_have_count(1)
    expect(page.locator("[data-panel='details']")).to_have_count(0)

    page.go_forward()
    expect(page).to_have_url(re.compile(r"/__tabs/details$"))
    expect(page.locator("[data-panel='details']")).to_have_count(1)
    expect(page.locator("[data-panel='default']")).to_have_count(0)

    # On a phone the navigation toggle shares the heading's row, and keeps
    # working after an htmx navigation replaces it.
    page.set_viewport_size(QA_VIEWPORTS[0])
    page.goto(list_url)
    toggle = page.get_by_role("button", name="Open navigation panel")
    expect(toggle).to_have_count(1)
    toggle_box = toggle.bounding_box()
    heading_box = page.locator("#main-content h1").bounding_box()
    assert toggle_box is not None
    assert heading_box is not None
    assert toggle_box["y"] < heading_box["y"] + heading_box["height"]
    assert heading_box["y"] < toggle_box["y"] + toggle_box["height"]
    page.locator(f"#main-content a[href$='/stubs/{stubs[3].pk}']:visible").first.click()
    expect(page.locator("#instance-title")).to_have_text("row-03")
    page.get_by_role("button", name="Open navigation panel").click()
    expect(page.locator("dialog[aria-label='Navigation']")).to_be_visible()

    # Layout at each viewport.
    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(list_url)
        assert_no_horizontal_overflow(page)
        is_phone = viewport["width"] < _PHONE_MAX_WIDTH
        sheet = page.locator("#stubs-sheet")
        expect(sheet).not_to_have_attribute("open", re.compile(".*"))

        # A table swap leaves the closed sheet hidden: the no-JavaScript
        # override once leaked into the page through the swapped fragment.
        page.locator("#stubs-q").fill("row")
        expect(page).to_have_url(re.compile(r"stubs-q=row"))
        _expect_swap_settled(page)
        expect(sheet).to_be_hidden()
        expect(sheet).not_to_have_attribute("open", re.compile(".*"))

        if is_phone:
            expect(page.locator("#stubs-table table")).to_be_hidden()
            expect(page.locator("#stubs-table ul li").first).to_be_visible()

            card_checkboxes = page.locator("#stubs-table ul li input[name='keys']")
            expect(card_checkboxes).to_have_count(PAGE_SIZE)
            card_checkboxes.first.check()
            expect(page.get_by_text("1 selected", exact=False)).to_be_visible()

            # "Sort" opens the one combined sheet; the inputs sit behind their
            # chip labels, so a tap lands on the label.
            page.get_by_role("button", name="Sort").click()
            page.locator("label", has_text="Name (descending)").click()
            page.locator("label", has_text="Alpha").click()
            page.get_by_role("button", name="Show results").click()
            expect(page).to_have_url(re.compile(r"stubs-sort=-name"))
            expect(page).to_have_url(re.compile(r"stubs-kind=a"))
        else:
            expect(page.locator("#stubs-table table")).to_be_visible()
            header = page.locator("#stubs-table thead th").filter(
                has=page.get_by_role("link", name="Name")
            )
            link = header.get_by_role("link", name="Name")
            # A sortable header label is not drawn in the link colour.
            assert link.evaluate("el => getComputedStyle(el).color") == header.evaluate(
                "el => getComputedStyle(el).color"
            )
            # A squeezed label does not shrink the sort icon to a dot.
            link.evaluate("el => { el.style.width = '2rem'; }")
            icon_width = link.locator("svg").evaluate(
                "el => el.getBoundingClientRect().width"
            )
            assert icon_width == 16


def test_filter_sheet_is_visible_with_javascript_off(
    browser: Browser,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    for i in range(3):
        make_stub(name=f"row-{i:02d}")

    with _no_js_page(browser, _PHONE_VIEWPORT) as no_js_page:
        no_js_page.goto(f"{live_server.url}{_LIST_PATH}")

        sheet = no_js_page.locator("#stubs-sheet")
        expect(sheet).to_be_visible()
        expect(sheet).to_have_css("opacity", "1")
        expect(sheet).to_have_css("transform", "none")


def test_bulk_action_posts_with_javascript_off(
    browser: Browser,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    for i in range(3):
        make_stub(name=f"row-{i:02d}")

    with _no_js_page(browser) as no_js_page:
        no_js_page.goto(f"{live_server.url}{_LIST_PATH}")

        row_checkboxes = no_js_page.locator("#stubs-table tbody input[name='keys']")
        row_checkboxes.nth(0).check()
        row_checkboxes.nth(1).check()
        no_js_page.get_by_role("button", name="Mark processed").click()
        expect(
            no_js_page.get_by_text("This will affect 2 stub models.")
        ).to_be_visible()

        no_js_page.get_by_role("button", name="Mark processed").click()
        expect(no_js_page).to_have_url(f"{live_server.url}{_FRAMEWORK_PATH}/stubs")

    active_by_name = dict(StubModel.objects.values_list("name", "is_active"))
    assert active_by_name["row-00"] is False
    assert active_by_name["row-01"] is False
    assert active_by_name["row-02"] is True
