"""E2E tests for row selection and bulk actions: the header checkbox's
tri-state behaviour, selection clearing on a table swap, and the whole
confirm-then-act flow with JavaScript off."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import Browser, Page, expect

from django.contrib.sites.models import Site

from ..conftest import StubModel, _make_stub


@pytest.fixture
def no_js_page(browser: Browser) -> Iterator[Page]:
    """A page in a fresh browser context with JavaScript disabled, for
    proving the bulk-action flow works without it."""
    context = browser.new_context(java_script_enabled=False)
    page = context.new_page()
    yield page
    context.close()


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_header_checkbox_tristate(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    [_make_stub(name=f"row-{i:02d}") for i in range(3)]

    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    header_checkbox = page.get_by_label("Select all on this page")
    row_checkboxes = page.locator("#stubs-table tbody input[name='keys']")
    expect(row_checkboxes).to_have_count(3)

    row_checkboxes.first.check()
    expect(header_checkbox).to_be_checked(indeterminate=True)

    row_checkboxes.nth(1).check()
    row_checkboxes.nth(2).check()
    expect(header_checkbox).to_be_checked()

    row_checkboxes.first.uncheck()
    header_checkbox.check()
    for i in range(3):
        expect(row_checkboxes.nth(i)).to_be_checked()


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_selection_clears_on_sort(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    [_make_stub(name=f"row-{i:02d}") for i in range(3)]

    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    row_checkboxes = page.locator("#stubs-table tbody input[name='keys']")
    row_checkboxes.first.check()
    expect(page.get_by_text("1 selected", exact=False)).to_be_visible()

    page.get_by_role("link", name="Name").click()

    expect(page.get_by_text("selected", exact=False)).to_be_hidden()
    expect(page.locator("#stubs-table tbody input[name='keys']:checked")).to_have_count(
        0
    )


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_stub_bulk_action_js_off(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    no_js_page: Page,
) -> None:
    """Checking rows, submitting, confirming and landing back on the table
    all work as native form submissions with no JavaScript at all."""
    [_make_stub(name=f"row-{i:02d}") for i in range(3)]
    page = no_js_page

    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    row_checkboxes = page.locator("#stubs-table tbody input[name='keys']")
    row_checkboxes.nth(0).check()
    row_checkboxes.nth(1).check()
    page.get_by_role("button", name="Mark processed").click()

    expect(page.get_by_text("This will affect 2 stub models.")).to_be_visible()

    page.get_by_role("button", name="Mark processed").click()

    expect(page).to_have_url(f"{live_server.url}/test-panel/framework/stubs")
    active_by_name = dict(StubModel.objects.values_list("name", "is_active"))
    assert active_by_name["row-00"] is False
    assert active_by_name["row-01"] is False
    assert active_by_name["row-02"] is True
