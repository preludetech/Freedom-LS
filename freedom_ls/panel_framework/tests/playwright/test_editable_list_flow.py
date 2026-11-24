"""Browser flow for the editable-list panel on the stub instance page.

The stub views have no authentication, so the flow needs no login.
"""

from __future__ import annotations

import re
import time

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import APIResponse, Locator, Page, Route, expect

from django.contrib.sites.models import Site

from ..helpers import make_stub, make_stub_entry
from ..stub_models import StubEntry
from .helpers import QA_VIEWPORTS, assert_no_horizontal_overflow, resize_viewport

pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def test_editable_list_flow(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    """One flow over the editable-list panel on the stub instance page.

    Proves that add, edit and remove update the list without a page load, with
    focus and announcer text; that an entry deleted behind the page's back is
    reported as unavailable; the cap line; "Add and add another"; the table
    layout's focus; that the dialogs stay inside the viewport; that a list
    without an Edit trigger announces and focuses the entry's Remove; that a
    slow refresh is not taken for the next Add's answer; that saving one entry
    twice announces both saves; and that each row and card lays out its Edit
    and Remove buttons tidily at every viewport on both layouts.
    """
    _check_add_edit_remove_without_a_page_load(page, live_server)
    _check_entry_without_an_edit_trigger(page, live_server)
    _check_slow_refresh_from_add_another(page, live_server)
    _check_saving_one_entry_twice(page, live_server)
    for tab in ("entries", "entries_table"):
        _check_footer_layout(page, live_server, tab)


def _check_add_edit_remove_without_a_page_load(
    page: Page, live_server: pytest_django.live_server_helper.LiveServer
) -> None:
    parent = make_stub(name="Parent")
    modal = page.locator("#app-modal")
    panel = page.locator("[data-panel='entries']")
    announcer = page.locator("#scope-announcer")

    page.goto(
        f"{live_server.url}/test-panel/framework/stubs/{parent.pk}/__tabs/entries"
    )
    page.evaluate("window.pageLoadMarker = 'still here'")
    expect(panel.get_by_text("No entries yet.")).to_be_visible()

    # Adding an entry shows it, puts focus on it and announces it.
    panel.get_by_role("button", name="Add stub entry").click()
    # htmx focuses the form's autofocus field again when the swap settles, so
    # typing into a second field before then lands in the first.
    expect(modal.get_by_label("Title")).to_be_visible()
    expect(page.locator("#app-modal-body")).not_to_have_class(
        re.compile(r"\bhtmx-settling\b")
    )
    modal.get_by_label("Title").fill("Alpha")
    modal.get_by_label("Detail").fill("first note")
    modal.get_by_role("button", name="Add", exact=True).click()
    expect(modal).to_be_hidden()
    expect(panel.get_by_text("Alpha")).to_be_visible()
    expect(panel.get_by_text("No entries yet.")).to_have_count(0)
    expect(panel.get_by_role("button", name="Edit Alpha, first note")).to_be_focused()
    expect(announcer).to_have_text("Added Alpha.")

    # Editing it shows the new title, puts focus on it and announces it.
    panel.get_by_role("button", name="Edit Alpha, first note").click()
    expect(modal.get_by_label("Title")).to_have_value("Alpha")
    modal.get_by_label("Title").fill("Beta")
    modal.get_by_role("button", name="Save").click()
    expect(modal).to_be_hidden()
    expect(panel.get_by_text("Beta")).to_be_visible()
    expect(panel.get_by_text("Alpha")).to_have_count(0)
    expect(panel.get_by_role("button", name="Edit Beta, first note")).to_be_focused()
    expect(announcer).to_have_text("Saved Beta.")

    # Cancelling an edit returns focus to its trigger and announces nothing.
    panel.get_by_role("button", name="Edit Beta, first note").click()
    expect(modal.get_by_label("Title")).to_have_value("Beta")
    modal.get_by_role("button", name="Cancel").click()
    expect(modal).to_be_hidden()
    expect(panel.get_by_role("button", name="Edit Beta, first note")).to_be_focused()
    expect(announcer).to_have_text("Saved Beta.")

    for title in ("Cora", "Dina"):
        panel.get_by_role("button", name="Add stub entry").click()
        modal.get_by_label("Title").fill(title)
        modal.get_by_role("button", name="Add", exact=True).click()
        expect(modal).to_be_hidden()
    expect(announcer).to_have_text("Added Dina.")

    # Removing a middle entry focuses the next one's Edit trigger.
    panel.get_by_role("button", name="Remove Cora").click()
    modal.get_by_role("button", name="Remove", exact=True).click()
    expect(modal).to_be_hidden()
    expect(panel.get_by_text("Cora")).to_have_count(0)
    expect(panel.get_by_role("button", name="Edit Dina")).to_be_focused()
    expect(announcer).to_have_text("Removed Cora.")

    # Removing the last entry focuses the previous one's Edit trigger.
    panel.get_by_role("button", name="Remove Dina").click()
    modal.get_by_role("button", name="Remove", exact=True).click()
    expect(modal).to_be_hidden()
    expect(panel.get_by_role("button", name="Edit Beta, first note")).to_be_focused()
    expect(announcer).to_have_text("Removed Dina.")

    # Removing the only entry focuses the empty state's Add trigger.
    panel.get_by_role("button", name="Remove Beta, first note").click()
    expect(modal.get_by_text("Removing Beta cannot be undone.")).to_be_visible()
    modal.get_by_role("button", name="Remove", exact=True).click()
    expect(modal).to_be_hidden()
    expect(panel.get_by_text("No entries yet.")).to_be_visible()
    expect(panel.get_by_role("button", name="Add stub entry")).to_be_focused()
    expect(announcer).to_have_text("Removed Beta.")

    # An entry deleted behind the page's back is reported as unavailable.
    panel.get_by_role("button", name="Add stub entry").click()
    modal.get_by_label("Title").fill("Zed")
    modal.get_by_role("button", name="Add", exact=True).click()
    expect(modal).to_be_hidden()
    expect(panel.get_by_role("button", name="Edit Zed")).to_be_visible()
    StubEntry.objects.filter(title="Zed").delete()
    panel.get_by_role("button", name="Edit Zed").click()
    expect(modal.get_by_text("This is no longer available")).to_be_visible()
    page.keyboard.press("Escape")
    expect(modal).to_be_hidden()

    # No step loaded a page.
    assert page.evaluate("window.pageLoadMarker") == "still here", (
        "a step loaded a page"
    )

    # A full list shows the cap line with focus on it and no Add trigger.
    page.goto(
        f"{live_server.url}/test-panel/framework/stubs/{parent.pk}/__tabs/entries_capped"
    )
    capped = page.locator("[data-panel='entries_capped']")
    for title in ("One", "Two"):
        capped.get_by_role("button", name="Add stub entry").click()
        modal.get_by_label("Title").fill(title)
        modal.get_by_role("button", name="Add", exact=True).click()
        expect(modal).to_be_hidden()
    expect(capped.locator("[data-editable-list-cap]")).to_be_focused()
    expect(capped.get_by_role("button", name="Add stub entry")).to_have_count(0)
    expect(announcer).to_have_text("Added Two.")

    # "Add and add another" stays in the dialog and announces through its own notice.
    empty_parent = make_stub(name="Empty parent")
    page.goto(
        f"{live_server.url}/test-panel/framework/stubs/{empty_parent.pk}/__tabs/entries_add_another"
    )
    another = page.locator("[data-panel='entries_add_another']")
    another.get_by_role("button", name="Add stub entry").click()
    modal.get_by_label("Title").fill("First")
    modal.get_by_role("button", name="Add and add another").click()
    expect(modal.locator("[data-status-message]")).to_have_text("Added First.")
    expect(modal.get_by_label("Title")).to_be_focused()
    expect(another.get_by_text("First")).to_be_visible()
    expect(announcer).to_have_text("")
    page.keyboard.press("Escape")
    expect(modal).to_be_hidden()
    expect(another.get_by_role("button", name="Add stub entry")).to_be_focused()

    # The table layout focuses the visible trigger of an entry drawn twice.
    table_parent = make_stub(name="Table parent")
    page.goto(
        f"{live_server.url}/test-panel/framework/stubs/{table_parent.pk}/__tabs/entries_table"
    )
    table = page.locator("[data-panel='entries_table']")
    table.get_by_role("button", name="Add stub entry").click()
    modal.get_by_label("Title").fill("Row")
    modal.get_by_role("button", name="Add", exact=True).click()
    expect(modal).to_be_hidden()
    expect(table.get_by_role("button", name="Edit Row")).to_be_focused()
    table.get_by_role("button", name="Remove Row").click()
    modal.get_by_role("button", name="Remove", exact=True).click()
    expect(modal).to_be_hidden()
    expect(table.get_by_role("button", name="Add stub entry")).to_be_focused()
    table.get_by_role("button", name="Add stub entry").click()
    modal.get_by_label("Title").fill("Kept")
    modal.get_by_role("button", name="Add", exact=True).click()
    expect(modal).to_be_hidden()

    for viewport in QA_VIEWPORTS:
        resize_viewport(page, viewport)
        assert_no_horizontal_overflow(page)
        for trigger in (
            table.get_by_role("button", name="Add stub entry"),
            table.get_by_role("button", name="Remove Kept"),
        ):
            trigger.click()
            expect(modal).to_be_visible()
            box = modal.bounding_box()
            assert box is not None
            assert box["x"] >= 0, (
                f"Dialog starts left of the viewport at {viewport['width']}px"
            )
            assert box["x"] + box["width"] <= viewport["width"], (
                f"Dialog runs past the right edge at {viewport['width']}px"
            )
            page.keyboard.press("Escape")
            expect(modal).to_be_hidden()


def _check_entry_without_an_edit_trigger(
    page: Page, live_server: pytest_django.live_server_helper.LiveServer
) -> None:
    """A person who may add and remove but not change still hears which entry
    changed, and focus lands on that entry's own trigger."""
    parent = make_stub(name="No edit parent")
    modal = page.locator("#app-modal")
    panel = page.locator("[data-panel='entries_no_edit']")
    announcer = page.locator("#scope-announcer")
    page.goto(
        f"{live_server.url}/test-panel/framework/stubs/{parent.pk}/__tabs/entries_no_edit"
    )

    for title in ("Alpha", "Beta"):
        panel.get_by_role("button", name="Add stub entry").click()
        modal.get_by_label("Title").fill(title)
        modal.get_by_role("button", name="Add", exact=True).click()
        expect(modal).to_be_hidden()
        expect(announcer).to_have_text(f"Added {title}.")
        expect(panel.get_by_role("button", name=f"Remove {title}")).to_be_focused()
    expect(panel.get_by_role("button", name="Edit Alpha")).to_have_count(0)

    # Removing an entry focuses the next entry's Remove trigger.
    panel.get_by_role("button", name="Remove Alpha").click()
    modal.get_by_role("button", name="Remove", exact=True).click()
    expect(modal).to_be_hidden()
    expect(announcer).to_have_text("Removed Alpha.")
    expect(panel.get_by_role("button", name="Remove Beta")).to_be_focused()


def _check_slow_refresh_from_add_another(
    page: Page, live_server: pytest_django.live_server_helper.LiveServer
) -> None:
    """The list's refresh after "Add and add another" arrives late, after the
    next plain Add has closed the dialog. It shows the list before that Add,
    so it must not be read as the Add's answer."""
    parent = make_stub(name="Slow refresh parent")
    modal = page.locator("#app-modal")
    panel = page.locator("[data-panel='entries_add_another']")
    announcer = page.locator("#scope-announcer")
    claimed: list[Route] = []
    held: list[tuple[Route, APIResponse]] = []

    def hold_first_panel_refresh(route: Route) -> None:
        if route.request.headers.get("hx-request") != "true" or claimed:
            route.continue_()
            return
        # Claimed before the fetch, so a request arriving mid-fetch is not held too.
        claimed.append(route)
        # Answered now, so it holds the list as it was, and handed back later.
        held.append((route, route.fetch()))

    page.goto(
        f"{live_server.url}/test-panel/framework/stubs/{parent.pk}/__tabs/entries_add_another"
    )
    page.route("**/__tabs/entries_add_another*", hold_first_panel_refresh)

    panel.get_by_role("button", name="Add stub entry").click()
    modal.get_by_label("Title").fill("Alpha")
    modal.get_by_role("button", name="Add and add another").click()
    expect(modal.locator("[data-status-message]")).to_have_text("Added Alpha.")
    modal.get_by_label("Title").fill("Beta")
    modal.get_by_role("button", name="Add", exact=True).click()
    expect(modal).to_be_hidden()
    # The route handler runs between Playwright calls, and its fetch can still
    # be in flight once the dialog has closed, so give it time to finish.
    deadline = time.monotonic() + 5
    while not held and time.monotonic() < deadline:
        page.wait_for_timeout(50)
    assert len(held) == 1, "the first list refresh was not held"

    # htmx queues the plain Add's refresh behind the held one, so it runs
    # once the stale list has landed.
    stale_route, stale_response = held[0]
    stale_route.fulfill(response=stale_response)

    expect(panel.get_by_text("Beta")).to_be_visible()
    expect(announcer).to_have_text("Added Beta.")
    expect(panel.get_by_role("button", name="Edit Beta")).to_be_focused()


def _check_saving_one_entry_twice(
    page: Page, live_server: pytest_django.live_server_helper.LiveServer
) -> None:
    """A live region whose text does not change is not read again, so the
    announcer is emptied before each message."""
    parent = make_stub(name="Twice parent")
    make_stub_entry(parent, "Alpha")
    modal = page.locator("#app-modal")
    panel = page.locator("[data-panel='entries']")
    announcer = page.locator("#scope-announcer")
    page.goto(
        f"{live_server.url}/test-panel/framework/stubs/{parent.pk}/__tabs/entries"
    )
    page.evaluate(
        """() => {
            window.announced = [];
            const region = document.getElementById("scope-announcer");
            new MutationObserver(() => window.announced.push(region.textContent))
                .observe(region, {childList: true, characterData: true, subtree: true});
        }"""
    )

    for _ in range(2):
        panel.get_by_role("button", name="Edit Alpha").click()
        modal.get_by_role("button", name="Save").click()
        expect(modal).to_be_hidden()
        expect(announcer).to_have_text("Saved Alpha.")
        expect(panel.get_by_role("button", name="Edit Alpha")).to_be_focused()

    # The announcer clears and refills a moment after the list refreshes, so
    # wait for the observer to have seen all three changes before comparing.
    page.wait_for_function("window.announced.length >= 3")

    # The region starts empty, so only the second save has a text to clear.
    assert page.evaluate("window.announced") == [
        "Saved Alpha.",
        "",
        "Saved Alpha.",
    ], "announcer did not clear and refill between the two saves"


def _check_footer_layout(
    page: Page, live_server: pytest_django.live_server_helper.LiveServer, tab: str
) -> None:
    """Every entry's Edit and Remove sit side by side under its title and
    detail, starting at the title's left edge, each as wide as its label, at
    the same offset on every entry whether or not it has a detail."""
    parent = make_stub(name=f"Footer parent {tab}")
    entries_and_details = {
        "Nomsa Dlamini": "Mother, 082 555 0101",
        "Pieter van Wyk": "Neighbour, 083 555 0142",
        "Aisha": "",
    }
    for title, detail in entries_and_details.items():
        make_stub_entry(parent, title, detail)

    page.goto(f"{live_server.url}/test-panel/framework/stubs/{parent.pk}/__tabs/{tab}")

    page.wait_for_load_state("networkidle")

    for viewport in QA_VIEWPORTS:
        width = viewport["width"]
        resize_viewport(page, viewport)
        entries = page.locator("li[data-editable-list-entry]:visible")
        if tab == "entries_table" and entries.count() == 0:
            # A wide container shows the table: the pair stays on one line in the last cell.
            for title in entries_and_details:
                edit_box = page.get_by_role(
                    "button", name=f"Edit {title}"
                ).bounding_box()
                remove_box = page.get_by_role(
                    "button", name=f"Remove {title}"
                ).bounding_box()
                assert edit_box is not None
                assert remove_box is not None
                assert edit_box["y"] == pytest.approx(remove_box["y"], abs=1), (
                    f"Edit and Remove of {title} not on one line in the table at {width}px"
                )
            continue
        assert entries.count() == len(entries_and_details), (
            f"Wrong visible entry count at {width}px on {tab}"
        )
        offsets: set[int] = set()
        for title, detail in entries_and_details.items():
            entry = entries.filter(has=page.get_by_role("button", name=f"Edit {title}"))
            title_box = entry.get_by_text(title, exact=True).bounding_box()
            text_box = (
                entry.get_by_text(detail, exact=True).bounding_box()
                if detail
                else title_box
            )
            edit_box = entry.get_by_role("button", name=f"Edit {title}").bounding_box()
            remove_box = entry.get_by_role(
                "button", name=f"Remove {title}"
            ).bounding_box()
            entry_box = entry.bounding_box()
            assert title_box is not None
            assert text_box is not None
            assert edit_box is not None
            assert remove_box is not None
            assert entry_box is not None
            assert edit_box["y"] == pytest.approx(remove_box["y"], abs=1), (
                f"Edit and Remove of {title} not on one line at {width}px on {tab}"
            )
            gap_under_text = edit_box["y"] - (text_box["y"] + text_box["height"])
            assert 8 <= gap_under_text <= 16, (
                f"Buttons of {title} not 8-16px under the text at {width}px on {tab}"
            )
            assert edit_box["x"] == pytest.approx(title_box["x"], abs=1), (
                f"Edit of {title} not at the title's left edge at {width}px on {tab}"
            )
            assert remove_box["x"] > edit_box["x"] + edit_box["width"], (
                f"Remove of {title} not beside Edit at {width}px on {tab}"
            )
            for name, box in (("Edit", edit_box), ("Remove", remove_box)):
                label_width = _label_width(
                    entry.get_by_role("button", name=f"{name} {title}")
                )
                assert box["width"] == pytest.approx(label_width, abs=1), (
                    f"{name} of {title} wider than its label at {width}px on {tab}"
                )
            offsets.add(round(edit_box["x"] - entry_box["x"]))
        assert len(offsets) == 1, (
            f"Button offsets differ between entries at {width}px on {tab}"
        )


def _label_width(button: Locator) -> float:
    """The width the button takes when sized to its own label and padding.

    A button laid out at this width is not stretched by its row, whatever
    the width of the font the browser picked for the label.
    """
    label_width: float = button.evaluate(
        """(el) => {
            const style = el.style.cssText;
            el.style.cssText +=
                ";flex:none!important;width:max-content!important"
                + ";min-width:0!important;max-width:none!important";
            const labelWidth = el.getBoundingClientRect().width;
            el.style.cssText = style;
            return labelWidth;
        }"""
    )
    return label_width
