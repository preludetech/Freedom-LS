"""E2E Playwright tests for the native #app-modal read-only fragment."""

from __future__ import annotations

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import Page, expect

from django.contrib.sites.models import Site

from ..conftest import _make_stub


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_opening_a_read_only_fragment_focuses_its_heading(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    stub = _make_stub(name="Read Only Target")
    page.goto(f"{live_server.url}/test-panel/framework/stubs/{stub.pk}/__tabs/details")

    page.get_by_role("button", name="View Info").click()

    expect(page.get_by_role("heading", name="Stub Info")).to_be_focused()


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_a_backdrop_click_closes_a_read_only_fragment(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    stub = _make_stub(name="Read Only Target")
    page.goto(f"{live_server.url}/test-panel/framework/stubs/{stub.pk}/__tabs/details")

    page.get_by_role("button", name="View Info").click()
    expect(page.locator("#app-modal")).to_be_visible()
    page.mouse.click(5, 5)

    expect(page.locator("#app-modal")).to_be_hidden()


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_a_click_in_the_dialogs_own_padding_leaves_a_read_only_fragment_open(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    stub = _make_stub(name="Read Only Target")
    page.goto(f"{live_server.url}/test-panel/framework/stubs/{stub.pk}/__tabs/details")

    page.get_by_role("button", name="View Info").click()
    expect(page.locator("#app-modal")).to_be_visible()
    page.locator("#app-modal").click(position={"x": 5, "y": 5})

    expect(page.locator("#app-modal")).to_be_visible()
