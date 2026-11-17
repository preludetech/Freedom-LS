"""Browser flows for the loading text of a form that carries a file.

Each case holds the upload request open with a route, so the button's in-flight
text can be read, then answers it. The stub views have no authentication, so
the flows need no login.
"""

from __future__ import annotations

import pytest
import pytest_django.live_server_helper
from playwright.sync_api import FilePayload, Locator, Page, Route, expect

from django.contrib.sites.models import Site

from ..helpers import make_stub

pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_FILE: FilePayload = {
    "name": "notes.txt",
    "mimeType": "text/plain",
    "buffer": b"some notes",
}


def _hold_requests(page: Page, action_name: str) -> list[Route]:
    """Park each POST to the action instead of answering it. The GET that
    opens the form goes through."""
    held: list[Route] = []

    def handle(route: Route) -> None:
        if route.request.method == "POST":
            held.append(route)
        else:
            route.fallback()

    page.route(f"**/__actions/{action_name}", handle)
    return held


def _submit_button(container: Locator) -> Locator:
    # The button's accessible name follows its in-flight text, so the submit
    # button is found by its type rather than by "Save".
    return container.locator("button[type=submit]:not([hidden])")


def _held_request(page: Page, held: list[Route], index: int) -> Route:
    """The index-th parked request, once the browser has sent it."""
    while len(held) <= index:
        page.wait_for_timeout(50)
    return held[index]


def _open_upload_tab(
    page: Page, live_server: pytest_django.live_server_helper.LiveServer
) -> None:
    stub = make_stub()
    page.goto(f"{live_server.url}/test-panel/framework/stubs/{stub.pk}/__tabs/upload")


def _open_dialog(page: Page) -> Locator:
    page.get_by_role("button", name="Upload", exact=True).click()
    dialog = page.locator("#app-modal")
    expect(dialog).to_be_visible()

    return dialog


def _submit_with_file(form: Locator, save: Locator) -> None:
    form.get_by_label("Title").fill("Notes")
    form.get_by_label("Attachment").set_input_files(_FILE)
    save.click()


def _submit_without_file(form: Locator, save: Locator) -> None:
    form.get_by_label("Title").fill("Notes")
    save.click()


def test_dialog_reads_uploading_while_a_file_goes_up(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    _open_upload_tab(page, live_server)
    held = _hold_requests(page, "upload")
    dialog = _open_dialog(page)
    save = _submit_button(dialog)

    _submit_with_file(dialog, save)

    expect(save).to_be_disabled()
    expect(save).to_have_text("Uploading…", use_inner_text=True)
    _held_request(page, held, 0).fulfill(status=204)


def test_dialog_reads_saving_when_no_file_is_chosen(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    _open_upload_tab(page, live_server)
    held = _hold_requests(page, "upload")
    dialog = _open_dialog(page)
    save = _submit_button(dialog)

    _submit_without_file(dialog, save)

    expect(save).to_be_disabled()
    expect(save).to_have_text("Saving…", use_inner_text=True)
    _held_request(page, held, 0).fulfill(status=204)


def test_dialog_reads_saving_after_a_failed_upload_is_cleared(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    _open_upload_tab(page, live_server)
    held = _hold_requests(page, "upload")
    dialog = _open_dialog(page)
    save = _submit_button(dialog)

    _submit_with_file(dialog, save)
    expect(save).to_have_text("Uploading…", use_inner_text=True)
    _held_request(page, held, 0).fulfill(status=500)
    expect(save).to_be_enabled()

    dialog.get_by_label("Attachment").set_input_files([])
    save.click()

    expect(save).to_have_text("Saving…", use_inner_text=True)
    _held_request(page, held, 1).fulfill(status=204)


def test_inline_form_reads_uploading_while_a_file_goes_up(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    _open_upload_tab(page, live_server)
    held = _hold_requests(page, "upload_inline")
    form = page.locator("#stub-upload-form")
    save = _submit_button(form)

    _submit_with_file(form, save)

    expect(save).to_be_disabled()
    expect(save).to_have_text("Uploading…", use_inner_text=True)
    _held_request(page, held, 0).fulfill(status=204)


def test_inline_form_reads_saving_when_no_file_is_chosen(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    _open_upload_tab(page, live_server)
    held = _hold_requests(page, "upload_inline")
    form = page.locator("#stub-upload-form")
    save = _submit_button(form)

    _submit_without_file(form, save)

    expect(save).to_be_disabled()
    expect(save).to_have_text("Saving…", use_inner_text=True)
    _held_request(page, held, 0).fulfill(status=204)


def test_inline_form_reads_saving_after_a_failed_upload_is_cleared(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    _open_upload_tab(page, live_server)
    held = _hold_requests(page, "upload_inline")
    form = page.locator("#stub-upload-form")
    save = _submit_button(form)

    _submit_with_file(form, save)
    expect(save).to_have_text("Uploading…", use_inner_text=True)
    _held_request(page, held, 0).fulfill(status=500)
    expect(save).to_be_enabled()

    form.get_by_label("Attachment").set_input_files([])
    save.click()

    expect(save).to_have_text("Saving…", use_inner_text=True)
    _held_request(page, held, 1).fulfill(status=204)
