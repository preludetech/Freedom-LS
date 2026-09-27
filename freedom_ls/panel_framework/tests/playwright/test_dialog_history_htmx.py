"""E2E Playwright test: an open #app-modal closes before an htmx navigation
caches the current page for history, so Back never restores it reopened.

A native modal dialog makes the rest of the page inert, so nothing outside
it — the sidebar included — can be clicked while it is open. The navigation
here is driven through htmx's own `htmx.ajax()` call instead of a literal
click, to exercise exactly what a sidebar link's hx-get/hx-push-url
attributes would trigger without fighting that (correct) platform behaviour.
"""

from __future__ import annotations

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import Page, expect

from django.contrib.sites.models import Site

from ..conftest import _make_stub


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_back_after_navigating_away_with_the_modal_open_restores_no_dialog(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    stub = _make_stub(name="History Target")
    list_url = f"{live_server.url}/test-panel/framework/stubs/"
    detail_url = f"{live_server.url}/test-panel/framework/stubs/{stub.pk}"
    page.goto(list_url)

    page.get_by_role("button", name="Create Item").click()
    expect(page.locator("#app-modal")).to_be_visible()

    page.evaluate(
        f"htmx.ajax('GET', '/test-panel/framework/stubs/{stub.pk}', "
        f"{{target: '#main-content', swap: 'outerHTML', "
        f"push: '/test-panel/framework/stubs/{stub.pk}'}})"
    )
    expect(page).to_have_url(detail_url)

    page.go_back()
    expect(page).to_have_url(list_url)
    expect(page.locator("#app-modal")).to_be_hidden()
