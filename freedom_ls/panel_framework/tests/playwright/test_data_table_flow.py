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
    # Name is the table's default sort, so the first click flips to descending.
    for sort_param in ("-name", "name", "-name"):
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
    expect(page).to_have_url(re.compile(r"stubs-sort=-name"))
    expect(page.locator("#stubs-table [data-table-anchor]")).to_be_focused()
    expect(page.locator("#stubs-search input[name='stubs-sort']")).to_have_count(1)
    expect(page.locator("[data-panel]")).to_have_count(1)
    expect_no_nested_panel(page, name="")
    expect(sheet).not_to_have_attribute("open", re.compile(".*"))

    # Paging keeps the sort param and does not nest frames.
    page2_link = _page_link(page, 2)
    expect(page2_link).to_have_attribute("href", re.compile(r"stubs-sort=-name"))
    expect(page2_link).to_have_attribute("href", re.compile(r"stubs-page=2"))
    page2_link.click()
    expect(page).to_have_url(re.compile(r"stubs-page=2"))
    expect(page).to_have_url(re.compile(r"stubs-sort=-name"))
    expect_no_nested_panel(page, name="")

    # Back restores the sorted, unpaged table in the URL and the rows.
    page.go_back()
    expect(page).to_have_url(re.compile(r"stubs-sort=-name"))
    expect(page).not_to_have_url(re.compile(r"stubs-page"))
    rows = page.locator("#stubs-table tbody tr")
    expect(rows.first).to_contain_text(f"row-{PAGE_SIZE + 4:02d}")

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
    expect(
        page.locator("[data-total-count]").get_by_text(f"{PAGE_SIZE} selected")
    ).to_be_visible()
    page.get_by_role("link", name="Name").click()
    expect(page.locator("#stubs-table").get_by_role("status")).to_have_text("")
    expect(page.locator("#stubs-table").get_by_role("searchbox")).to_be_visible()
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
    expect(modal.locator("#bulk-result-headline")).to_have_text(
        "2 stub models changed."
    )
    expect(modal.locator("#bulk-result-headline")).to_be_visible()
    modal.get_by_role("button", name="Close", exact=True).first.click()
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
            expect(
                page.locator("[data-total-count]").get_by_text("1 selected")
            ).to_be_visible()
            # The bar takes the toolbar's place; Clear brings the toolbar back.
            page.locator("[data-total-count]").get_by_role(
                "button", name="Clear", exact=True
            ).click()

            # The phone toolbar buttons and the pager meet the 44px touch target.
            for control in (
                page.get_by_role("button", name="Filter"),
                page.get_by_role("button", name="Sort"),
                page.get_by_role("link", name="Next", exact=True),
            ):
                box = control.bounding_box()
                assert box is not None
                assert box["height"] >= 44, f"{control} is {box['height']}px high"

            # "Sort" opens a menu of columns; choosing the sorted column again
            # flips its direction. "Filter" opens the sheet, whose inputs sit
            # behind their chip labels, so a tap lands on the label.
            page.get_by_role("button", name="Sort").click()
            page.get_by_role("menuitem", name="Name").click()
            expect(page).to_have_url(re.compile(r"stubs-sort=-name"))
            page.get_by_role("button", name="Filter").click()
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


def test_more_actions_menu_stays_inside_the_viewport(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    """The "More actions" menu once opened off the screen, leaving its last
    item out of reach."""
    for i in range(PAGE_SIZE):
        make_stub(name=f"row-{i:02d}")
    list_url = f"{live_server.url}{_LIST_PATH}"

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(list_url)
        page.locator("#stubs-table input[name='keys']:visible").first.check()
        more = page.get_by_role("button", name="More actions")
        chevron = more.locator("svg")
        expect(chevron).to_have_css("rotate", "none")
        more.click()
        # The chevron turns up while the menu is open.
        expect(chevron).to_have_css("rotate", "180deg")
        last_item = (
            page.get_by_role("menu", name="More actions").get_by_role("menuitem").last
        )
        expect(last_item).to_be_visible()
        box = last_item.bounding_box()
        assert box is not None
        assert box["y"] >= 0, f"menu item above the viewport at {viewport}"
        assert box["y"] + box["height"] <= viewport["height"], (
            f"menu item below the viewport at {viewport}"
        )


_IS_TOPMOST = """el => {
    const box = el.getBoundingClientRect();
    return document.elementFromPoint(
        box.x + box.width / 2, box.y + box.height / 2) === el;
}"""


def test_selection_bar_sticks_above_the_table_at_every_width(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    """The bar sat above the table on the desktop and at the bottom of the
    viewport below lg. It has one place at every width: above the table, in
    the toolbar's row, sticking under the header while the page scrolls."""
    for i in range(PAGE_SIZE + 1):
        make_stub(name=f"row-{i:02d}")
    list_url = f"{live_server.url}{_LIST_PATH}"
    bar = page.locator("[data-total-count]")

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(list_url)
        checkboxes = page.locator("#stubs-table input[name='keys']:visible")
        checkboxes.first.check()
        expect(bar).to_be_visible()

        assert bar.evaluate("el => getComputedStyle(el).position") == "sticky", (
            f"bar position at {viewport}"
        )
        bar_bottom = bar.evaluate("el => el.getBoundingClientRect().bottom")
        first_top = checkboxes.first.evaluate("el => el.getBoundingClientRect().top")
        assert bar_bottom <= first_top, f"bar below the first row at {viewport}"

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        box = bar.bounding_box()
        assert box is not None
        assert 0 <= box["y"] < viewport["height"] / 2, (
            f"bar scrolled out of view at {viewport}"
        )
        assert page.get_by_role("link", name="Next", exact=True).evaluate(
            _IS_TOPMOST
        ), f"bar covers the pager at {viewport}"


def _tops_after_click(control: Locator) -> list[float]:
    """Click a control inside the table region and read the table's top
    over the next six frames."""
    tops: list[float] = control.evaluate(
        """async control => {
            const table = control.closest('[data-table-region]').querySelector('table');
            const frame = () => new Promise(resolve => requestAnimationFrame(resolve));
            control.click();
            const tops = [];
            for (let i = 0; i < 6; i++) {
                await frame();
                tops.push(table.getBoundingClientRect().top);
            }
            return tops;
        }"""
    )
    return tops


def test_the_bar_takes_the_toolbars_place_at_every_width(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    """The selection bar replaces the toolbar in its row without moving the
    table; Clear brings the toolbar back. Below lg it does the same."""
    for i in range(PAGE_SIZE):
        make_stub(name=f"row-{i:02d}")
    list_url = f"{live_server.url}{_LIST_PATH}"
    table = page.locator("#stubs-table")
    bar = page.locator("[data-total-count]")
    search = table.get_by_role("searchbox")
    row_checkboxes = table.locator("tbody input[name='keys']")
    top_of_table = "el => el.querySelector('table').getBoundingClientRect().top"

    page.set_viewport_size(QA_VIEWPORTS[2])
    page.goto(list_url)
    expect(bar).to_be_hidden()
    expect(search).to_be_visible()
    top_before = table.evaluate(top_of_table)

    # The toolbar and the bar swap in one frame: sampled frame by frame, a
    # swap a frame apart leaves the table a row higher or lower for that frame.
    assert _tops_after_click(row_checkboxes.first) == [top_before] * 6
    expect(bar).to_be_visible()
    expect(search).to_be_hidden()

    assert (
        _tops_after_click(bar.get_by_role("button", name="Clear", exact=True))
        == [top_before] * 6
    )
    expect(bar).to_be_hidden()
    expect(search).to_be_visible()
    expect(table.locator("tbody input[name='keys']:checked")).to_have_count(0)
    assert table.evaluate(top_of_table) == top_before

    page.set_viewport_size(QA_VIEWPORTS[1])
    page.goto(list_url)
    page.locator("#stubs-table input[name='keys']:visible").first.check()
    expect(bar).to_be_visible()
    expect(search).to_be_hidden()


def test_selection_bar_actions_fieldset_draws_no_box(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    """The fieldset wrapping the bulk-action buttons picked up the global
    fieldset border and padding, boxing the buttons and, on a phone, making
    the fixed selection bar cover a large part of the screen."""
    make_stub(name="row-00")
    page.set_viewport_size(_PHONE_VIEWPORT)
    page.goto(f"{live_server.url}{_LIST_PATH}")
    page.locator("#stubs-table input[name='keys']:visible").first.check()

    actions = page.locator("[data-total-count] fieldset")
    expect(actions).to_be_visible()
    box_styles = actions.evaluate(
        """el => {
            const s = getComputedStyle(el);
            return [s.borderTopWidth, s.paddingTop, s.paddingLeft, s.borderTopLeftRadius];
        }"""
    )
    assert box_styles == ["0px", "0px", "0px", "0px"]


def test_clearing_the_bar_returns_focus_to_the_page_checkbox(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    """Emptying the selection hides the bar that held focus, so focus goes to
    the page checkbox on screen: the header's on desktop, the card list's on
    a phone."""
    for i in range(PAGE_SIZE + 3):
        make_stub(name=f"row-{i:02d}")
    list_url = f"{live_server.url}{_LIST_PATH}"
    table = page.locator("#stubs-table")
    bar = page.locator("[data-total-count]")
    clear = bar.get_by_role("button", name="Clear", exact=True)
    select_all = bar.get_by_role("button", name=re.compile(r"^(Select|Deselect) all"))

    page.set_viewport_size(QA_VIEWPORTS[2])
    page.goto(list_url)
    header_checkbox = table.locator("thead").get_by_label("Select all on this page")
    table.locator("tbody input[name='keys']").first.check()
    clear.click()
    expect(header_checkbox).to_be_focused()

    table.locator("tbody input[name='keys']").first.check()
    # A partial selection leaves the bar checkbox unchecked and indeterminate,
    # so it is ticked to cover the page before it is unticked.
    bar_checkbox = bar.get_by_label("Select page")
    bar_checkbox.check()
    bar_checkbox.uncheck()
    expect(header_checkbox).to_be_focused()

    page.set_viewport_size(QA_VIEWPORTS[0])
    page.goto(list_url)
    card_checkbox = table.locator(".md\\:hidden").get_by_label(
        "Select all on this page"
    )
    cards = table.locator("ul li input[name='keys']")
    cards.first.check()
    clear.click()
    expect(card_checkbox).to_be_focused()

    cards.first.check()
    select_all.click()
    select_all.click()
    expect(select_all).to_be_hidden()
    expect(card_checkbox).to_be_focused()


def test_select_all_matching_spans_every_page(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    matching = 2 * PAGE_SIZE + 3
    for i in range(matching):
        make_stub(name=f"pick-{i:02d}")
    for i in range(4):
        make_stub(name=f"other-{i}")
    filtered_url = f"{live_server.url}{_LIST_PATH}?stubs-q=pick"
    page.set_viewport_size(QA_VIEWPORTS[2])
    page.goto(filtered_url)

    # The status region exists before anything is ticked.
    status = page.locator("#stubs-table").get_by_role("status")
    expect(status).to_have_count(1)
    row_checkboxes = page.locator("#stubs-table tbody input[name='keys']")
    expect(row_checkboxes).to_have_count(PAGE_SIZE)
    bar = page.locator("[data-total-count]")
    select_all = bar.get_by_role("button", name=re.compile(r"^(Select|Deselect) all"))
    header_checkbox = page.locator("#stubs-table thead").get_by_label(
        "Select all on this page"
    )
    bar_checkbox = bar.get_by_label("Select page")
    expect(select_all).to_be_hidden()

    # Ticking one row offers to select every match.
    row_checkboxes.first.check()
    expect(status).to_have_text("1 selected")
    expect(select_all).to_have_text(f"Select all {matching}")

    # Selecting every match flips the link and keeps both page checkboxes checked.
    select_all.click()
    expect(status).to_have_text(f"{matching} selected")
    expect(select_all).to_have_text("Deselect all")
    expect(
        page.get_by_text("Changing page, sort or filters clears the selection.")
    ).to_be_visible()
    expect(header_checkbox).to_be_checked()
    expect(bar_checkbox).to_be_checked()

    # Unticking one row leaves every other matching row selected.
    row_checkboxes.first.uncheck()
    expect(status).to_have_text(f"{matching - 1} selected")
    expect(select_all).to_have_text(f"Select all {matching}")
    expect(header_checkbox).to_be_checked(indeterminate=True)
    expect(bar_checkbox).to_be_checked(indeterminate=True)
    select_all.click()
    expect(row_checkboxes.first).to_be_checked()
    expect(status).to_have_text(f"{matching} selected")

    select_all.click()
    expect(status.get_by_text("selected")).to_be_hidden()
    row_checkboxes.first.check()
    row_checkboxes.nth(1).check()
    select_all.click()
    row_checkboxes.first.uncheck()
    expect(status).to_have_text(f"{matching - 1} selected")

    bar.get_by_role("button", name="Mark processed").click()
    modal = page.locator("#app-modal")
    expect(
        modal.get_by_text(f"This will affect {matching - 1} stub models.")
    ).to_be_visible()
    modal.get_by_role("button", name="Mark processed").click()
    expect(modal.locator("#bulk-result-headline")).to_have_text(
        f"{matching - 1} stub models changed."
    )
    expect(modal.locator("#bulk-result-headline")).to_be_visible()
    assert StubModel.objects.filter(is_active=False).count() == matching - 1
    assert StubModel.objects.get(name="pick-00").is_active
    assert not StubModel.objects.filter(
        name__startswith="other", is_active=False
    ).exists()

    # Sorting swaps the table and clears the selection.
    page.goto(filtered_url)
    header_checkbox.check()
    select_all.click()
    expect(status).to_have_text(f"{matching} selected")
    page.get_by_role("link", name="Name").click()
    expect(status.get_by_text("selected")).to_be_hidden()
    expect(page.locator("#stubs-table tbody input[name='keys']:checked")).to_have_count(
        0
    )

    # Clear after Select all hides the bar; the next selection starts in page mode.
    header_checkbox.check()
    select_all.click()
    bar.get_by_role("button", name="Clear", exact=True).click()
    expect(status.get_by_text("selected")).to_be_hidden()
    expect(page.locator("#stubs-table").get_by_role("searchbox")).to_be_visible()
    row_checkboxes.first.check()
    expect(status).to_have_text("1 selected")
    expect(select_all).to_have_text(f"Select all {matching}")

    # Deselect all hides the bar and unticks every row.
    select_all.click()
    select_all.click()
    expect(status.get_by_text("selected")).to_be_hidden()
    expect(page.locator("#stubs-table tbody input[name='keys']:checked")).to_have_count(
        0
    )

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(filtered_url)
        assert_no_horizontal_overflow(page)


def test_select_all_on_a_single_page_table_stays_in_page_mode(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    rows = PAGE_SIZE - 1
    for i in range(rows):
        make_stub(name=f"row-{i:02d}")
    page.set_viewport_size(QA_VIEWPORTS[2])
    page.goto(f"{live_server.url}{_LIST_PATH}")

    status = page.locator("#stubs-table").get_by_role("status")
    bar = page.locator("[data-total-count]")
    row_checkboxes = page.locator("#stubs-table tbody input[name='keys']")
    row_checkboxes.first.check()
    bar.get_by_role("button", name=f"Select all {rows}").click()

    expect(page.locator("#stubs-table tbody input[name='keys']:checked")).to_have_count(
        rows
    )
    expect(bar.get_by_role("button", name="Deselect all")).to_be_visible()
    expect(status).to_have_text(f"{rows} selected")
    expect(page.locator("input[name='mode']")).to_have_value("keys")


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
        # The selection controls need JavaScript; only the actions remain.
        expect(
            no_js_page.get_by_role("button", name=re.compile("Select all"))
        ).to_have_count(0)
        expect(
            no_js_page.get_by_role("button", name="Clear", exact=True)
        ).to_have_count(0)
        expect(no_js_page.get_by_text(" selected")).to_have_count(0)
        no_js_page.get_by_role("button", name="Mark processed").click()
        # The confirmation is the same modal JavaScript opens, over the list.
        modal = no_js_page.locator("#app-modal")
        expect(modal).to_be_visible()
        expect(modal.get_by_text("This will affect 2 stub models.")).to_be_visible()
        expect(modal.get_by_role("link", name="Cancel")).to_be_visible()
        expect(no_js_page.locator("#stubs-table")).to_be_attached()

        modal.get_by_role("button", name="Mark processed").click()
        expect(no_js_page).to_have_url(f"{live_server.url}{_FRAMEWORK_PATH}/stubs")
        expect(no_js_page.get_by_text("2 stub models changed.")).to_be_visible()

    active_by_name = dict(StubModel.objects.values_list("name", "is_active"))
    assert active_by_name["row-00"] is False
    assert active_by_name["row-01"] is False
    assert active_by_name["row-02"] is True


def test_the_bar_covers_nothing_with_javascript_off(
    browser: Browser,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    """With JavaScript off the bar always shows, under the toolbar, and
    sticks there: scrolled to the end, the pager's Next link is not under it."""
    for i in range(PAGE_SIZE + 1):
        make_stub(name=f"row-{i:02d}")

    with _no_js_page(browser) as no_js_page:
        for viewport in QA_VIEWPORTS:
            no_js_page.set_viewport_size(viewport)
            no_js_page.goto(f"{live_server.url}{_LIST_PATH}")

            bar = no_js_page.locator("[data-total-count]")
            assert bar.evaluate("el => getComputedStyle(el).position") == "sticky"

            no_js_page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            assert no_js_page.get_by_role("link", name="Next", exact=True).evaluate(
                _IS_TOPMOST
            ), f"bar covers the pager at {viewport}"


def test_more_actions_trigger_is_hidden_with_javascript_off(
    browser: Browser,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    """The More actions menu opens through Alpine, so its trigger used to show inert."""
    for i in range(3):
        make_stub(name=f"row-{i:02d}")

    with _no_js_page(browser) as no_js_page:
        no_js_page.goto(f"{live_server.url}{_LIST_PATH}")
        no_js_page.locator("#stubs-table tbody input[name='keys']").nth(0).check()

        expect(no_js_page.get_by_role("button", name="Mark processed")).to_be_visible()
        expect(no_js_page.get_by_role("button", name="More actions")).to_be_hidden()

        # In its place a <details> menu opens without script, never loose buttons.
        more = no_js_page.locator("[data-total-count] details")
        menu = more.get_by_role("menu", name="More actions")
        expect(menu).to_be_hidden()
        more.locator("summary").click()
        expect(menu).to_be_visible()
        expect(menu.get_by_role("menuitem").first).to_be_visible()


def test_a_row_detail_opens_and_closes_by_mouse_and_keyboard(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    stubs = [make_stub(name=f"row-{i:02d}", kind="a") for i in range(PAGE_SIZE + 2)]
    detail_url = f"{live_server.url}{_FRAMEWORK_PATH}/stubs/{stubs[0].pk}/__tabs/detail"
    page.set_viewport_size(QA_VIEWPORTS[2])
    page.goto(detail_url)
    table = page.locator("#detail-table table")
    first = table.get_by_role("button", name="More about row-00")
    second = table.get_by_role("button", name="More about row-01")
    first_detail = table.get_by_text("Detail for row-00")
    second_detail = table.get_by_text("Detail for row-01")

    expect(first_detail).to_be_hidden()
    first.click()
    expect(first_detail).to_be_visible()
    expect(first).to_have_attribute("aria-expanded", "true")

    # A second row opens without closing the first.
    second.click()
    expect(second_detail).to_be_visible()
    expect(first_detail).to_be_visible()

    first.focus()
    page.keyboard.press("Enter")
    expect(first_detail).to_be_hidden()
    expect(first).to_have_attribute("aria-expanded", "false")
    expect(first).to_be_focused()
    expect(second_detail).to_be_visible()

    # Fetching a page replaces the table, so every row starts closed.
    _page_link(page, 2).click()
    expect(page).to_have_url(re.compile(r"detail-page=2$"))
    _expect_swap_settled(page)
    page.locator("#detail-table").get_by_role(
        "link", name="1", exact=True
    ).first.click()
    expect(page).not_to_have_url(re.compile(r"detail-page=2"))
    _expect_swap_settled(page)
    expect(table.get_by_role("button", name="More about row-01")).to_have_attribute(
        "aria-expanded", "false"
    )
    expect(table.get_by_text("Detail for row-01")).to_be_hidden()

    # On a phone the card's chevron opens and closes its detail too.
    page.set_viewport_size(_PHONE_VIEWPORT)
    cards = page.locator("#detail-table ul")
    card_toggle = cards.get_by_role("button", name="More about row-00")
    card_detail = cards.get_by_text("Detail for row-00")
    expect(card_detail).to_be_hidden()
    card_toggle.click()
    expect(card_detail).to_be_visible()
    expect(card_toggle).to_have_attribute("aria-expanded", "true")
    card_toggle.click()
    expect(card_detail).to_be_hidden()
    expect(card_toggle).to_have_attribute("aria-expanded", "false")
