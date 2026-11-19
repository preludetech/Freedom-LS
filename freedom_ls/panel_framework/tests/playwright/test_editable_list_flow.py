"""Browser flow for the editable-list panel on the stub instance page.

The stub views have no authentication, so the flow needs no login.
"""

from __future__ import annotations

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import Page, expect

from django.contrib.sites.models import Site

from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

from ..helpers import make_stub

pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def test_editable_list_adds_edits_and_removes_without_a_page_load(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    parent = make_stub(name="Parent")
    modal = page.locator("#app-modal")
    panel = page.locator("[data-panel='entries']")

    page.goto(
        f"{live_server.url}/test-panel/framework/stubs/{parent.pk}/__tabs/entries"
    )
    page.evaluate("window.pageLoadMarker = 'still here'")
    expect(panel.get_by_text("No entries yet.")).to_be_visible()

    # Adding an entry shows it in the list.
    panel.get_by_role("button", name="Add stub entry").click()
    modal.get_by_label("Title").fill("Alpha")
    modal.get_by_label("Detail").fill("first note")
    modal.get_by_role("button", name="Add", exact=True).click()
    expect(modal).to_be_hidden()
    expect(panel.get_by_text("Alpha")).to_be_visible()
    expect(panel.get_by_text("No entries yet.")).to_have_count(0)

    # Editing it shows the new title.
    panel.get_by_role("button", name="Edit Alpha, first note").click()
    expect(modal.get_by_label("Title")).to_have_value("Alpha")
    modal.get_by_label("Title").fill("Beta")
    modal.get_by_role("button", name="Save").click()
    expect(modal).to_be_hidden()
    expect(panel.get_by_text("Beta")).to_be_visible()
    expect(panel.get_by_text("Alpha")).to_have_count(0)

    # Removing it shows the empty state.
    panel.get_by_role("button", name="Remove Beta, first note").click()
    expect(modal.get_by_text("Removing Beta cannot be undone.")).to_be_visible()
    modal.get_by_role("button", name="Remove", exact=True).click()
    expect(modal).to_be_hidden()
    expect(panel.get_by_text("No entries yet.")).to_be_visible()

    # No step loaded a page.
    assert page.evaluate("window.pageLoadMarker") == "still here"

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(page)
