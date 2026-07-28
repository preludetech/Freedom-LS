"""E2E Playwright tests for list-view table refresh (Bug 3).

Tests that 'Save and add another' causes the table to refresh without a full
page reload, and that the create button is not duplicated after repeated
creates.

Note: the test panel URL has no authentication middleware, and
``StubCreateAction.has_permission`` always returns True (see stub_panels.py),
so the create button appears for anonymous users in the test environment.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_save_and_add_another_refreshes_table(
    live_server,
    live_server_site,
    page: Page,
) -> None:
    """'Save and add another' creates a row and the table refreshes with it,
    no full-page reload needed. The create button is not duplicated after
    repeated creates.
    """
    # Navigate to the list view (no auth required — test URL has no auth middleware)
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    # Confirm table is present
    table = page.locator("#data-table-container")
    expect(table).to_have_count(1)

    # Confirm create button is present exactly once
    expect(page.get_by_role("button", name="Create Item")).to_have_count(1)

    # --- First create ---
    page.get_by_role("button", name="Create Item").click()
    # Fill the name field in the modal
    page.get_by_label("Name").fill("Alpha")
    # Click "Save and add another"
    page.get_by_role("button", name="Save and add another").click()

    # Table should refresh — "Alpha" row must appear without full page reload
    expect(table.get_by_text("Alpha")).to_be_visible()

    # --- Second create ---
    page.get_by_label("Name").fill("Beta")
    page.get_by_role("button", name="Save and add another").click()

    # Both rows must be present
    expect(table.get_by_text("Alpha")).to_be_visible()
    expect(table.get_by_text("Beta")).to_be_visible()

    # Create button must not be duplicated
    expect(page.get_by_role("button", name="Create Item")).to_have_count(1)
