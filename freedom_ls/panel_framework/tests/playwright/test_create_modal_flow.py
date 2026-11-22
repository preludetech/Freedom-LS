"""Browser flow for the shared ``#app-modal`` create form.

The stub list view has no authentication, so the flow needs no login.
"""

from __future__ import annotations

import re

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import Locator, Page, Route, expect

from django.contrib.sites.models import Site

from ..helpers import make_stub
from ..stub_models import StubModel
from ..stub_panels import StubDataTable
from .assertions import expect_no_nested_panel
from .helpers import QA_VIEWPORTS, assert_no_horizontal_overflow

pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_LIST_PATH = "/test-panel/framework/stubs/"
# Viewports narrower than Tailwind's `sm` breakpoint show the modal as a bottom sheet.
_PHONE_MAX_WIDTH = 640


def _open_create_modal(page: Page) -> Locator:
    """Open the create modal and wait for htmx to finish settling it.

    htmx focuses the fragment's [autofocus] field again when the swap settles,
    just after it lands. Typing or pressing Esc inside that window would lose
    focus from the discard confirmation to that late refocus.
    """
    page.get_by_role("button", name="Create Item").first.click()
    name_field = page.locator("#app-modal").get_by_label("Name")
    expect(name_field).to_be_visible()
    expect(page.locator("#app-modal-body")).not_to_have_class(
        re.compile(r"htmx-settling")
    )
    return name_field


def _name_cells(page: Page) -> Locator:
    """The Name column of the stub table (second cell, after the checkbox).

    The Kind column's choices are also labelled Alpha/Beta, so cell text must
    be matched in this column only.
    """
    return page.locator("#stubs-table tbody tr td:nth-child(2)")


def test_create_modal_flow(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    """The create modal from open to submit, then its layout and submit guards.

    Proves focus on open, Esc and the discard prompt, Cancel, the error summary
    taking focus, "Add and add another", backdrop and close-control behaviour,
    Enter submitting as Add, history entries after Add, the modal's layout at
    each viewport (wrapped footer actions stay right-aligned on a phone), both
    submits disabling while the create POST is held, and a double-click on Add
    posting once.
    """
    page_size = StubDataTable.get_page_size()
    make_stub(name="Existing")
    for i in range(page_size + 5):
        make_stub(name=f"row-{i:02d}")
    list_url = f"{live_server.url}{_LIST_PATH}"
    modal = page.locator("#app-modal")
    create_button = page.get_by_role("button", name="Create Item")

    page.goto(list_url)
    expect(page.locator("[data-panel=''] #stubs-table")).to_have_count(1)
    expect(create_button).to_have_count(1)

    # Opening focuses the name field.
    name_field = _open_create_modal(page)
    expect(name_field).to_be_focused()

    # Esc on a clean form closes the modal.
    page.keyboard.press("Escape")
    expect(modal).to_be_hidden()

    # Esc on a dirty form swaps the dialog to a discard confirmation.
    name_field = _open_create_modal(page)
    name_field.fill("Dirty")
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog", name="Discard changes?")).to_be_visible()
    expect(name_field).to_be_hidden()
    expect(page.get_by_role("button", name="Cancel")).to_be_hidden()
    expect(
        modal.get_by_text("The changes you made haven't been saved.")
    ).to_be_visible()
    expect(page.get_by_role("button", name="Keep editing")).to_be_focused()

    # Keep editing brings the form back with its input.
    page.get_by_role("button", name="Keep editing").click()
    expect(page.get_by_role("button", name="Keep editing")).to_be_hidden()
    expect(page.get_by_role("dialog", name="Create Item")).to_be_visible()
    expect(name_field).to_have_value("Dirty")
    expect(name_field).to_be_focused()

    # A second Esc asks again instead of closing the dialog.
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog", name="Discard changes?")).to_be_visible()
    page.get_by_role("button", name="Keep editing").click()
    expect(name_field).to_have_value("Dirty")

    # The header close control asks the same question as Esc; the footer
    # Cancel does not (below).
    page.locator("#app-modal-body").get_by_role("button", name="Close").click()
    page.get_by_role("button", name="Discard").click()
    expect(modal).to_be_hidden()
    name_field = _open_create_modal(page)
    expect(name_field).to_have_value("")

    # Cancel on a clean form closes the modal and returns focus to the trigger.
    page.get_by_role("button", name="Cancel").click()
    expect(modal).to_be_hidden()
    expect(create_button).to_be_focused()

    # Cancel on a dirty form closes without asking.
    name_field = _open_create_modal(page)
    name_field.fill("Dirty")
    page.get_by_role("button", name="Cancel").click()
    expect(modal).to_be_hidden()
    expect(page.get_by_role("dialog", name="Discard changes?")).to_be_hidden()

    # A duplicate name moves focus to the error summary.
    name_field = _open_create_modal(page)
    name_field.fill("Existing")
    page.get_by_role("button", name="Add", exact=True).click()
    expect(page.locator("[data-error-summary]")).to_be_focused()

    # Fixing the name and choosing "Add and add another" leaves a blank form.
    # The reader is on page 2, and rows sort by name, so "zz-" rows land there.
    page.get_by_role("button", name="Cancel").click()
    expect(modal).to_be_hidden()
    page.locator("#stubs-table").get_by_role("link", name="2", exact=True).click()
    expect(page).to_have_url(re.compile(r"stubs-page=2"))
    page2_url = page.url
    history_length = page.evaluate("history.length")

    name_field = _open_create_modal(page)
    name_field.fill("zz-alpha")
    page.get_by_role("button", name="Add and add another").click()
    expect(_name_cells(page).get_by_text("zz-alpha", exact=True)).to_be_visible()
    expect(modal).to_be_visible()
    expect(name_field).to_have_value("")

    # The refresh keeps the page, adds no history entry, leaves focus off the
    # table and does not nest panels or duplicate the create button.
    expect(page).to_have_url(page2_url)
    assert page.evaluate("history.length") == history_length
    expect(page.locator("#stubs-table [data-table-anchor]")).not_to_be_focused()
    expect(create_button).to_have_count(1)
    expect_no_nested_panel(page, name="")

    # A second create keeps both rows.
    name_field.fill("zz-beta")
    page.get_by_role("button", name="Add and add another").click()
    expect(_name_cells(page).get_by_text("zz-beta", exact=True)).to_be_visible()
    expect(_name_cells(page).get_by_text("zz-alpha", exact=True)).to_be_visible()
    expect(create_button).to_have_count(1)
    expect_no_nested_panel(page, name="")

    # A backdrop click does not close a form. The viewport corner is clear of
    # the centred dialog, so the click lands on its ::backdrop.
    page.mouse.click(5, 5)
    expect(modal).to_be_visible()

    # The close control on a dirty form asks before closing.
    name_field.fill("Dirty")
    page.locator("#app-modal-body").get_by_role("button", name="Close").click()
    expect(page.get_by_role("dialog", name="Discard changes?")).to_be_visible()
    page.get_by_role("button", name="Keep editing").click()
    expect(name_field).to_have_value("Dirty")

    # Enter in the name field submits as Add, not "Add and add another".
    name_field.fill("zz-delta")
    name_field.press("Enter")
    expect(page.locator("#instance-title")).to_have_text("zz-delta")
    expect(modal).to_be_hidden()
    delta = StubModel.objects.get(name="zz-delta")
    detail_url = f"{live_server.url}{_LIST_PATH}{delta.pk}"
    expect(page).to_have_url(detail_url)
    expect(page.locator("#main-content")).to_be_focused()

    # Add closes the modal and the navigation has a history entry.
    page.go_back()
    expect(page).to_have_url(page2_url)
    name_field = _open_create_modal(page)
    name_field.fill("zz-gamma")
    page.get_by_role("button", name="Add", exact=True).click()
    expect(modal).to_be_hidden()
    gamma = StubModel.objects.get(name="zz-gamma")
    expect(page).to_have_url(f"{live_server.url}{_LIST_PATH}{gamma.pk}")
    expect(page.locator("#instance-title")).to_have_text("zz-gamma")
    expect(page.locator("#main-content")).to_be_focused()
    page.go_back()
    expect(page).to_have_url(page2_url)

    # Layout at each viewport.
    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(list_url)
        _open_create_modal(page)
        assert_no_horizontal_overflow(page)

        is_phone = viewport["width"] < _PHONE_MAX_WIDTH
        if is_phone:
            # The slide-up transition ends with no transform applied.
            expect(modal).to_have_css("transform", "none")
        box = modal.bounding_box()
        assert box is not None
        right_gap = viewport["width"] - (box["x"] + box["width"])
        bottom_gap = viewport["height"] - (box["y"] + box["height"])
        if is_phone:
            assert box["x"] == pytest.approx(0, abs=2)
            assert right_gap == pytest.approx(0, abs=2)
            assert bottom_gap == pytest.approx(0, abs=2)
        else:
            assert box["x"] == pytest.approx(right_gap, abs=2)
            assert box["y"] == pytest.approx(bottom_gap, abs=2)

        close_box = (
            page.locator("#app-modal-body").get_by_role("button", name="Close")
        ).bounding_box()
        assert close_box is not None
        assert box["x"] <= close_box["x"] <= box["x"] + box["width"]
        assert box["y"] <= close_box["y"] <= box["y"] + box["height"]
        if not is_phone:
            # The corner is the top-right one, not merely somewhere inside.
            assert close_box["x"] > box["x"] + box["width"] / 2
            assert close_box["y"] < box["y"] + box["height"] / 2

        heights: list[float] = []
        for button in page.locator("#app-modal-body form button:not([hidden])").all():
            button_box = button.bounding_box()
            assert button_box is not None
            assert button_box["x"] >= box["x"]
            assert button_box["x"] + button_box["width"] <= box["x"] + box["width"]
            heights.append(button_box["height"])
        # A label that word-wraps makes its button a whole line taller.
        assert max(heights) < 1.5 * min(heights)

        if viewport["width"] == 375:
            footer = page.locator("#app-modal [data-modal-footer]:visible")
            footer_box = footer.bounding_box()
            last_box = footer.locator("button:visible").last.bounding_box()
            cancel_box = footer.get_by_role("button", name="Cancel").bounding_box()
            assert footer_box is not None
            assert last_box is not None
            assert cancel_box is not None
            assert last_box["y"] > cancel_box["y"] + cancel_box["height"] - 1, (
                "footer actions did not wrap below Cancel at 375px"
            )
            # The footer has px-6 (24px) padding.
            assert last_box["x"] + last_box["width"] == pytest.approx(
                footer_box["x"] + footer_box["width"] - 24, abs=1
            ), "wrapped footer actions not right-aligned at 375px"

        page.keyboard.press("Escape")
        expect(modal).to_be_hidden()

    # The handler only parks the route: a handler that blocks also blocks the
    # assertions below, which then run after the response has arrived.
    held: list[Route] = []
    page.goto(list_url)
    name_field = _open_create_modal(page)
    name_field.fill("Beta")
    page.route("**/__actions/create_item", lambda route: held.append(route))

    # Located by CSS, not accessible name: the clicked button's own label
    # swaps to its loading text once the request is in flight.
    submit_buttons = page.locator("#app-modal-body button[type='submit']:not([hidden])")
    add_another_button = submit_buttons.nth(0)
    add_button = submit_buttons.nth(1)
    add_button.click()

    expect(
        add_another_button, "Add and add another enabled while create is pending"
    ).to_be_disabled()
    expect(add_button, "Add enabled while create is pending").to_be_disabled()

    for _ in range(100):
        if held:
            break
        page.wait_for_timeout(50)
    held[0].continue_()
    expect(modal).to_be_hidden()
    page.unroute("**/__actions/create_item")

    post_count = {"total": 0}

    def _count_then_continue(route: Route) -> None:
        post_count["total"] += 1
        route.continue_()

    page.goto(list_url)
    name_field = _open_create_modal(page)
    name_field.fill("Gamma")
    page.route("**/__actions/create_item", _count_then_continue)

    page.get_by_role("button", name="Add", exact=True).dblclick()

    expect(modal).to_be_hidden()
    assert post_count["total"] == 1, "double-clicking Add posted more than once"
    assert StubModel.objects.filter(name="Gamma").count() == 1, (
        "double-clicking Add created more than one row"
    )
    page.unroute("**/__actions/create_item")
