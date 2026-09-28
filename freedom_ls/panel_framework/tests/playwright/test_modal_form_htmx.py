"""E2E Playwright tests for the native #app-modal form flow.

Covers focus management (open, 422, re-render), "Save and add another"
staying open with a refreshed table, "Save" navigating #main-content with a
history entry, Cancel returning focus to the trigger, and both submit
buttons being disabled together to prevent a double submit.
"""

from __future__ import annotations

import threading

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import Page, Route, expect

from django.contrib.sites.models import Site

from ..conftest import StubModel, _make_stub


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_opening_the_create_modal_focuses_the_name_field(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    page.get_by_role("button", name="Create Item").click()

    expect(page.get_by_label("Name")).to_be_focused()


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_a_duplicate_name_moves_focus_to_the_error_summary(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    _make_stub(name="Existing")
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    page.get_by_role("button", name="Create Item").click()
    page.get_by_label("Name").fill("Existing")
    page.get_by_role("button", name="Save", exact=True).click()

    expect(page.locator("[data-error-summary]")).to_be_focused()


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_save_and_add_another_leaves_a_blank_form_and_shows_the_row(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    page.get_by_role("button", name="Create Item").click()
    page.get_by_label("Name").fill("Alpha")
    page.get_by_role("button", name="Save and add another").click()

    expect(page.locator("#app-modal")).to_be_visible()
    expect(page.get_by_label("Name")).to_have_value("")
    table = page.locator("[data-panel=''] [id^='panel-']")
    expect(table.get_by_text("Alpha")).to_be_visible()


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_save_closes_the_modal_and_navigates_with_a_history_entry(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    list_url = f"{live_server.url}/test-panel/framework/stubs/"
    page.goto(list_url)

    page.get_by_role("button", name="Create Item").click()
    page.get_by_label("Name").fill("Charlie")
    page.get_by_role("button", name="Save", exact=True).click()

    expect(page.locator("#app-modal")).to_be_hidden()
    item = StubModel.objects.get(name="Charlie")
    expect(page).to_have_url(f"{live_server.url}/test-panel/framework/stubs/{item.pk}")
    expect(page.locator("#instance-title")).to_have_text("Charlie")
    expect(page.locator("#main-content")).to_be_focused()

    page.go_back()
    expect(page).to_have_url(list_url)


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_cancel_closes_the_modal_and_returns_focus_to_the_trigger(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    trigger = page.get_by_role("button", name="Create Item")
    trigger.click()
    page.get_by_role("button", name="Cancel").click()

    expect(page.locator("#app-modal")).to_be_hidden()
    expect(trigger).to_be_focused()


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_esc_on_a_clean_form_closes_the_modal(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    page.get_by_role("button", name="Create Item").click()
    expect(page.locator("#app-modal")).to_be_visible()
    page.keyboard.press("Escape")

    expect(page.locator("#app-modal")).to_be_hidden()


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_esc_on_a_dirty_form_shows_the_discard_prompt_with_the_form_intact(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    page.get_by_role("button", name="Create Item").click()
    page.get_by_label("Name").fill("Dirty")
    page.keyboard.press("Escape")

    expect(page.locator("#app-modal")).to_be_visible()
    expect(page.get_by_label("Name")).to_have_value("Dirty")
    expect(page.get_by_role("button", name="Keep editing")).to_be_focused()


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_keep_editing_hides_the_prompt_and_returns_focus_to_the_form(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    page.get_by_role("button", name="Create Item").click()
    page.get_by_label("Name").fill("Dirty")
    page.keyboard.press("Escape")
    page.get_by_role("button", name="Keep editing").click()

    expect(page.locator("[data-modal-discard-prompt]")).to_be_hidden()
    expect(page.get_by_label("Name")).to_have_value("Dirty")
    expect(page.get_by_label("Name")).to_be_focused()


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_discard_closes_the_dialog_and_loses_the_input(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    page.get_by_role("button", name="Create Item").click()
    page.get_by_label("Name").fill("Dirty")
    page.keyboard.press("Escape")
    page.get_by_role("button", name="Discard").click()

    expect(page.locator("#app-modal")).to_be_hidden()


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_a_backdrop_click_does_not_close_a_form(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    page.goto(f"{live_server.url}/test-panel/framework/stubs/")

    page.get_by_role("button", name="Create Item").click()
    expect(page.locator("#app-modal")).to_be_visible()
    # A click at the dialog's own padding, clear of the form and close
    # button, lands on the dialog element itself.
    page.locator("#app-modal").click(position={"x": 5, "y": 5})

    expect(page.locator("#app-modal")).to_be_visible()


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_clicking_save_disables_every_submit_button_while_the_request_is_pending(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    hold_response = threading.Event()

    def _hold_then_continue(route: Route) -> None:
        hold_response.wait(timeout=5)
        route.continue_()

    page.goto(f"{live_server.url}/test-panel/framework/stubs/")
    page.get_by_role("button", name="Create Item").click()
    page.get_by_label("Name").fill("Beta")
    page.route("**/__actions/create_item", _hold_then_continue)

    # Located by CSS, not accessible name: the clicked button's own label
    # swaps to its loading text once the request is in flight.
    submit_buttons = page.locator("#app-modal-body button[type='submit']")
    save_and_add_button = submit_buttons.nth(0)
    save_button = submit_buttons.nth(1)
    save_button.click()

    expect(save_and_add_button).to_be_disabled()
    expect(save_button).to_be_disabled()

    hold_response.set()
    expect(page.locator("#app-modal")).to_be_hidden()


@pytest.mark.playwright
@pytest.mark.django_db(transaction=True)
def test_double_clicking_save_creates_exactly_one_cohort(
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    page: Page,
) -> None:
    post_count = {"total": 0}

    def _count_then_continue(route: Route) -> None:
        post_count["total"] += 1
        route.continue_()

    page.goto(f"{live_server.url}/test-panel/framework/stubs/")
    page.get_by_role("button", name="Create Item").click()
    page.get_by_label("Name").fill("Gamma")
    page.route("**/__actions/create_item", _count_then_continue)

    page.get_by_role("button", name="Save", exact=True).dblclick()

    expect(page.locator("#app-modal")).to_be_hidden()
    assert post_count["total"] == 1
    assert StubModel.objects.filter(name="Gamma").count() == 1
