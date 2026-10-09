"""E2E tests for the mobile card layout: cards replace the table below md,
the filter & sort sheet applies state as a GET form, and card checkboxes
drive the selection bar the same way row checkboxes do on desktop."""

from __future__ import annotations

import re

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import Page, expect

from django.contrib.sites.models import Site

from ..helpers import make_stub

_PHONE_VIEWPORT = {"width": 390, "height": 844}


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_cards_visible_and_table_hidden_on_phone(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    [make_stub(name=f"row-{i:02d}") for i in range(3)]

    page.set_viewport_size(_PHONE_VIEWPORT)
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    expect(page.locator("#stubs-table table")).to_be_hidden()
    expect(page.locator("#stubs-table ul li").first).to_be_visible()


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_sheet_applies_filter_and_sort(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    [make_stub(name=f"row-{i:02d}", kind="a") for i in range(2)]

    page.set_viewport_size(_PHONE_VIEWPORT)
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    # "Filter" and "Sort" both open the one combined sheet, so opening it
    # from either button reaches both sets of controls. The radio/checkbox
    # inputs are visually hidden behind their chip labels, so clicking the
    # label (as a real tap would) is what actually lands on the target.
    page.get_by_role("button", name="Sort").click()
    page.locator("label", has_text="Name (descending)").click()
    page.locator("label", has_text="Alpha").click()
    page.get_by_role("button", name="Show results").click()

    expect(page).to_have_url(re.compile(r"stubs-sort=-name"))
    expect(page).to_have_url(re.compile(r"stubs-kind=a"))


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_card_checkboxes_drive_the_bar(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    [make_stub(name=f"row-{i:02d}") for i in range(3)]

    page.set_viewport_size(_PHONE_VIEWPORT)
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    card_checkboxes = page.locator("#stubs-table ul li input[name='keys']")
    expect(card_checkboxes).to_have_count(3)

    card_checkboxes.first.check()

    expect(page.get_by_text("1 selected", exact=False)).to_be_visible()
