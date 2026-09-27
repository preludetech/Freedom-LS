"""E2E Playwright tests for the native #app-modal delete-confirmation flow."""

from __future__ import annotations

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import Page, expect

from django.contrib.sites.models import Site

from ..conftest import StubModel, _make_stub


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_cancel_has_initial_focus(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    stub = _make_stub(name="Deletable")
    page.goto(f"{live_server.url}/test-panel/framework/stubs/{stub.pk}/__tabs/details")

    page.get_by_role("button", name="Delete", exact=True).click()

    expect(page.get_by_role("button", name="Cancel")).to_be_focused()


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_delete_closes_the_modal_and_navigates_to_the_list(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    stub = _make_stub(name="Deletable")
    list_url = f"{live_server.url}/test-panel/framework/stubs"
    page.goto(f"{live_server.url}/test-panel/framework/stubs/{stub.pk}/__tabs/details")

    page.get_by_role("button", name="Delete", exact=True).click()
    # Scoped to the dialog: the trigger with the same name sits behind it,
    # outside #app-modal.
    dialog = page.locator("#app-modal")
    dialog.get_by_role("button", name="Delete", exact=True).click()

    expect(page.locator("#app-modal")).to_be_hidden()
    expect(page).to_have_url(list_url)
    assert not StubModel.objects.filter(pk=stub.pk).exists()
