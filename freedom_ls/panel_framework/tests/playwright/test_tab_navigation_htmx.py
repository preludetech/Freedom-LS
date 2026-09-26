"""Tab switching in a browser: the URL, the visible tab and history agree.

A tab click fetches through htmx and pushes the tab's own URL. Back and
Forward refetch that URL, which renders the full page with the right tab.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from ..conftest import _make_stub
from .assertions import expect_no_nested_panel


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_tab_switch_back_and_forward_keep_url_and_tab_together(
    live_server,
    live_server_site,
    page: Page,
) -> None:
    stub = _make_stub(name="Tabbed Stub")
    instance_url = f"{live_server.url}/test-panel/framework/stubs/{stub.pk}"
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
    expect(page).to_have_url(re.compile(rf"/stubs/{stub.pk}$"))
    expect(page.locator("[data-panel='default']")).to_have_count(1)
    expect(page.locator("[data-panel='details']")).to_have_count(0)

    page.go_forward()
    expect(page).to_have_url(re.compile(r"/__tabs/details$"))
    expect(page.locator("[data-panel='details']")).to_have_count(1)
    expect(page.locator("[data-panel='default']")).to_have_count(0)
