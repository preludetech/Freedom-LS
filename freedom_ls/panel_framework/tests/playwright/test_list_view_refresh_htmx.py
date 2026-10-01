"""E2E Playwright tests for list-view table refresh (Bug 3).

Tests that 'Save and add another' causes the table to refresh without a full
page reload, and that the create button is not duplicated after repeated
creates.

Note: the test panel URL has no authentication middleware, and
``StubCreateAction.has_permission`` always returns True regardless of the
context it is asked about (see stub_panels.py), so the create button appears
for anonymous users in the test environment.
"""

from __future__ import annotations

import re

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import Page, expect

from django.contrib.sites.models import Site

from ..conftest import _make_stub
from ..stub_panels import StubDataTable
from .assertions import expect_no_nested_panel


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_save_and_add_another_refreshes_table(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    """'Save and add another' creates a row and the table refreshes with it,
    no full-page reload needed. The create button is not duplicated after
    repeated creates.
    """
    # Navigate to the list view (no auth required — test URL has no auth middleware)
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    # Confirm table is present
    table = page.locator("[data-panel=''] #stubs-table")
    expect(table).to_have_count(1)

    # Confirm create button is present exactly once
    expect(page.get_by_role("button", name="Create Item")).to_have_count(1)

    # --- First create ---
    page.get_by_role("button", name="Create Item").click()
    # Fill the name field in the modal. Scoped to the dialog: the table's own
    # mobile filter-and-sort sheet also has a "Name" (ascending/descending)
    # label, and it stays in the DOM even while closed.
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Name").fill("Alpha")
    # Click "Save and add another"
    page.get_by_role("button", name="Save and add another").click()

    # Table should refresh — "Alpha" row must appear without full page reload.
    # The Name column specifically (its second cell, after the selection
    # checkbox): StubModel's "kind" choices are also labelled Alpha/Beta, so
    # a freshly-created row's default Kind cell reads "Alpha" too.
    name_cell = table.locator("tbody tr td:nth-child(2)")
    expect(name_cell.get_by_text("Alpha", exact=True)).to_be_visible()

    # --- Second create ---
    dialog.get_by_label("Name").fill("Beta")
    page.get_by_role("button", name="Save and add another").click()

    # Both rows must be present
    expect(name_cell.get_by_text("Alpha", exact=True)).to_be_visible()
    expect(name_cell.get_by_text("Beta", exact=True)).to_be_visible()

    # Create button must not be duplicated
    expect(page.get_by_role("button", name="Create Item")).to_have_count(1)
    expect_no_nested_panel(page, name="")


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_save_and_add_another_keeps_current_page(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    """A refresh after 'Save and add another' re-renders the page the reader
    is on, keeps it in the address bar, and adds no history entry."""
    page_size = StubDataTable.page_size
    [_make_stub(name=f"row-{i:02d}") for i in range(page_size + 5)]

    page.goto(f"{live_server.url}/test-panel/framework/stubs/")
    table = page.locator("#stubs-table")
    table.get_by_role("link", name="2", exact=True).click()
    expect(page).to_have_url(re.compile(r"stubs-page=2"))
    history_length = page.evaluate("history.length")

    page.get_by_role("button", name="Create Item").click()
    page.get_by_role("dialog").get_by_label("Name").fill("zz-new")
    page.get_by_role("button", name="Save and add another").click()

    # Rows sort by name, so the new row lands on page 2 with the old tail.
    expect(page.locator("#stubs-table")).to_contain_text("zz-new")
    expect(page.locator("#stubs-table")).to_contain_text(f"row-{page_size + 4:02d}")
    expect(page).to_have_url(re.compile(r"stubs-page=2"))
    assert page.evaluate("history.length") == history_length


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_save_and_add_another_leaves_focus_off_the_table(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    """The list refresh after 'Save and add another' must not pull focus out
    of the still-open create modal onto the table behind it."""
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    page.get_by_role("button", name="Create Item").click()
    page.get_by_role("dialog").get_by_label("Name").fill("Alpha")
    page.get_by_role("button", name="Save and add another").click()

    table = page.locator("#stubs-table")
    expect(
        table.locator("tbody tr td:nth-child(2)").get_by_text("Alpha", exact=True)
    ).to_be_visible()
    expect(table.locator("[data-table-anchor]")).not_to_be_focused()
