"""E2E Playwright tests: an open dialog closes before an htmx navigation
caches the current page for history, so Back never restores it reopened.

A native modal dialog makes the rest of the page inert, so nothing outside
it — the sidebar included — can be clicked while it is open. #app-modal's
test therefore drives the navigation through htmx's own `htmx.ajax()` call
instead of a literal click, to exercise exactly what a sidebar link's
hx-get/hx-push-url attributes would trigger without fighting that (correct)
platform behaviour. The desktop #quick-view drawer is opened with show(),
not showModal(), so it is never modal and the sidebar stays genuinely
clickable — its test follows a real link instead.
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


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_back_after_navigating_away_with_the_quick_view_open_restores_no_dialog(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    stub = _make_stub(name="History Target")
    # No trailing slash: that's what the sidebar's own reverse()d link uses.
    list_url = f"{live_server.url}/test-panel/framework/stubs"
    detail_url = f"{live_server.url}/test-panel/framework/stubs/{stub.pk}"
    # Starting from the detail page rather than the list means the sidebar's
    # "Stubs" link below leads somewhere genuinely different, so htmx pushes
    # a real second entry for Back to unwind. StubBaseConfig, the sidebar's
    # other section, requires an authenticated request and this suite runs
    # anonymously by design, so it is not a usable destination here.
    page.goto(detail_url)

    # The sidebar's own expanded instance entry also reads "History Target"
    # on this page, so the quick-view trigger is scoped by its attribute
    # rather than by role name alone.
    page.locator('a[aria-controls="quick-view"]', has_text="History Target").click()
    expect(page.locator("#quick-view")).to_be_visible()

    page.get_by_label("Sections").get_by_role("link", name="Stubs", exact=True).click()
    expect(page).to_have_url(list_url)

    page.go_back()
    expect(page).to_have_url(detail_url)
    expect(page.locator("#quick-view")).to_be_hidden()


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_a_history_restore_swap_raises_no_page_error(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    """With historyCacheSize 0 every Back is a server-side restore, whose
    htmx:afterSwap carries no detail.target. Whether a still-live listener
    sees it depends on when Alpine tears the old page down, so the event is
    dispatched directly rather than raced through a real Back."""
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")
    expect(page.locator("#app-modal")).to_be_attached()

    page.evaluate(
        "document.body.dispatchEvent(new CustomEvent('htmx:afterSwap', "
        "{bubbles: true, detail: {elt: document.body}}))"
    )

    assert page_errors == []
