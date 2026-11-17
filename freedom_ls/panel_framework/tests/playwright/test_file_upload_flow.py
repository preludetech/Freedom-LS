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


_TOO_LARGE_MESSAGE = "The file may be too large to upload. Choose a smaller file."
_GENERIC_MESSAGE = "Your changes could not be saved. Try again."
_FAILURES = [(413, _TOO_LARGE_MESSAGE), (500, _GENERIC_MESSAGE)]


@pytest.mark.parametrize(("status", "message"), _FAILURES)
def test_dialog_shows_the_request_error_and_can_be_saved_again(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
    status: int,
    message: str,
) -> None:
    _open_upload_tab(page, live_server)
    held = _hold_requests(page, "upload")
    dialog = _open_dialog(page)
    save = _submit_button(dialog)

    _submit_with_file(dialog, save)
    _held_request(page, held, 0).fulfill(status=status, body="Server error")

    alert = dialog.get_by_role("alert")
    expect(alert).to_have_text(message)
    expect(dialog.locator("[data-request-error]")).to_be_focused()
    expect(dialog).to_be_visible()
    expect(dialog.get_by_label("Title")).to_have_value("Notes")
    expect(save).to_be_enabled()

    save.click()
    _held_request(page, held, 1).fulfill(status=204)

    expect(alert).to_have_count(0)


@pytest.mark.parametrize(("status", "message"), _FAILURES)
def test_inline_form_shows_the_request_error_and_keeps_what_was_typed(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
    status: int,
    message: str,
) -> None:
    _open_upload_tab(page, live_server)
    held = _hold_requests(page, "upload_inline")
    form = page.locator("#stub-upload-form")
    save = _submit_button(form)

    _submit_with_file(form, save)
    _held_request(page, held, 0).fulfill(status=status, body="Server error")

    expect(form.get_by_role("alert")).to_have_text(message)
    expect(form.get_by_label("Title")).to_have_value("Notes")
    expect(save).to_be_enabled()


def test_dialog_without_a_file_field_shows_the_generic_request_error(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    make_stub()
    held = _hold_requests(page, "create_item")
    page.goto(f"{live_server.url}/test-panel/framework/stubs")
    page.get_by_role("button", name="Create Item").click()
    dialog = page.locator("#app-modal")
    expect(dialog).to_be_visible()

    dialog.get_by_label("Name").fill("Widget")
    dialog.get_by_role("button", name="Save", exact=True).click()
    _held_request(page, held, 0).fulfill(status=500, body="Server error")

    expect(dialog.get_by_role("alert")).to_have_text(_GENERIC_MESSAGE)


def test_dialog_shows_the_generic_request_error_when_the_request_cannot_be_sent(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    _open_upload_tab(page, live_server)
    held = _hold_requests(page, "upload")
    dialog = _open_dialog(page)

    _submit_without_file(dialog, _submit_button(dialog))
    _held_request(page, held, 0).abort()

    expect(dialog.get_by_role("alert")).to_have_text(_GENERIC_MESSAGE)


def test_dialog_shows_no_request_error_when_the_page_reloads_for_a_404(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    _open_upload_tab(page, live_server)
    held = _hold_requests(page, "upload")
    dialog = _open_dialog(page)

    _submit_without_file(dialog, _submit_button(dialog))
    with page.expect_navigation():
        _held_request(page, held, 0).fulfill(status=404, body="Not found")

    expect(page.get_by_text(_GENERIC_MESSAGE)).to_have_count(0)
    expect(page.get_by_text(_TOO_LARGE_MESSAGE)).to_have_count(0)


def test_escape_closes_the_dialog_when_nothing_has_changed(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    _open_upload_tab(page, live_server)
    dialog = _open_dialog(page)

    page.keyboard.press("Escape")

    expect(dialog).to_be_hidden()


def test_choosing_a_file_makes_escape_ask_before_discarding(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    _open_upload_tab(page, live_server)
    dialog = _open_dialog(page)
    attachment = dialog.get_by_label("Attachment")
    attachment.set_input_files(_FILE)

    page.keyboard.press("Escape")

    expect(page.get_by_role("dialog", name="Discard changes?")).to_be_visible()
    page.get_by_role("button", name="Keep editing").click()
    expect(dialog).to_be_visible()
    assert attachment.evaluate("input => input.files[0].name") == "notes.txt"


def test_clearing_a_chosen_file_makes_escape_close_without_asking(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    _open_upload_tab(page, live_server)
    dialog = _open_dialog(page)
    attachment = dialog.get_by_label("Attachment")
    attachment.set_input_files(_FILE)
    attachment.set_input_files([])

    page.keyboard.press("Escape")

    expect(dialog).to_be_hidden()
    expect(page.get_by_role("dialog", name="Discard changes?")).to_have_count(0)


def _computed_colour(locator: Locator) -> str:
    return str(locator.evaluate("el => getComputedStyle(el).color"))


@pytest.mark.parametrize("container_selector", ["dialog[open]", "#stub-upload-form"])
def test_request_error_message_is_drawn_in_the_holder_error_colour(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
    container_selector: str,
) -> None:
    """The alert inserted into the request-error holder used to take the body
    text colour from the base paragraph rule instead of the error colour."""
    _open_upload_tab(page, live_server)
    inline = container_selector == "#stub-upload-form"
    held = _hold_requests(page, "upload_inline" if inline else "upload")
    container = page.locator("#stub-upload-form") if inline else _open_dialog(page)
    save = _submit_button(container)

    _submit_with_file(container, save)
    _held_request(page, held, 0).fulfill(status=500, body="Server error")

    alert = container.get_by_role("alert")
    expect(alert).to_have_text(_GENERIC_MESSAGE)
    holder = container.locator("[data-request-error]")
    assert _computed_colour(alert) == _computed_colour(holder)
