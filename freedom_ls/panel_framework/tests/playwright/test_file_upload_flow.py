"""Browser flows for the loading text and request errors of a form that carries a file.

Each case holds the upload request open with a route, so the button's in-flight
text can be read, then answers it, and removes the route. The stub views have
no authentication, so the flows need no login.
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


def _release_requests(page: Page, action_name: str) -> None:
    page.unroute(f"**/__actions/{action_name}")


def _submit_button(container: Locator) -> Locator:
    # The button's accessible name follows its in-flight text, so the submit
    # button is found by its type rather than by "Save".
    return container.locator("button[type=submit]:not([hidden])")


def _inline_submit_button(page: Page) -> Locator:
    # The inline form's Save sits in the card footer, outside the form.
    return page.locator("#stub-upload-form-submit")


def _held_request(page: Page, held: list[Route], index: int) -> Route:
    """The index-th parked request, once the browser has sent it."""
    while len(held) <= index:
        page.wait_for_timeout(50)
    return held[index]


def _open_upload_tab(
    page: Page, live_server: pytest_django.live_server_helper.LiveServer, stub_pk: int
) -> None:
    page.goto(f"{live_server.url}/test-panel/framework/stubs/{stub_pk}/__tabs/upload")


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


_TOO_LARGE_MESSAGE = "The file may be too large to upload. Choose a smaller file."
_GENERIC_MESSAGE = "Your changes could not be saved. Try again."
_FAILURES = [(413, _TOO_LARGE_MESSAGE), (500, _GENERIC_MESSAGE)]


def _computed_colour(locator: Locator) -> str:
    return str(locator.evaluate("el => getComputedStyle(el).color"))


def test_file_upload_dialog_flow(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    """The upload dialog's request handling, each case from a fresh load.

    Proves that the button reads "Uploading..." while a file goes up, "Saving..."
    with no file and after a failed upload is cleared; that 413 and 500 show
    the matching alert with focus on it and the form can be saved again; that
    a dialog with no file field shows the generic error on a 500; that an
    aborted request and a scripted 403 show the generic error; that a response
    carrying a toast adds no request error; that Escape closes a clean dialog,
    asks before discarding a chosen file and closes after the file is cleared;
    that the alert is drawn in the holder's error colour; and that a 404
    reloads the page with no error alert.
    """
    stub = make_stub()

    _open_upload_tab(page, live_server, stub.pk)
    held = _hold_requests(page, "upload")
    dialog = _open_dialog(page)
    save = _submit_button(dialog)
    _submit_with_file(dialog, save)
    expect(save, "button not disabled while a file uploads").to_be_disabled()
    expect(save, "button text while a file uploads").to_have_text(
        "Uploading…", use_inner_text=True
    )
    _held_request(page, held, 0).fulfill(status=204)
    _release_requests(page, "upload")

    _open_upload_tab(page, live_server, stub.pk)
    held = _hold_requests(page, "upload")
    dialog = _open_dialog(page)
    save = _submit_button(dialog)
    _submit_without_file(dialog, save)
    expect(save, "button not disabled while saving without a file").to_be_disabled()
    expect(save, "button text with no file chosen").to_have_text(
        "Saving…", use_inner_text=True
    )
    _held_request(page, held, 0).fulfill(status=204)
    _release_requests(page, "upload")

    _open_upload_tab(page, live_server, stub.pk)
    held = _hold_requests(page, "upload")
    dialog = _open_dialog(page)
    save = _submit_button(dialog)
    _submit_with_file(dialog, save)
    expect(save, "button text while a file uploads before failing").to_have_text(
        "Uploading…", use_inner_text=True
    )
    _held_request(page, held, 0).fulfill(status=500)
    expect(save, "button not re-enabled after a failed upload").to_be_enabled()
    dialog.get_by_label("Attachment").set_input_files([])
    save.click()
    expect(save, "button text after a failed upload is cleared").to_have_text(
        "Saving…", use_inner_text=True
    )
    _held_request(page, held, 1).fulfill(status=204)
    _release_requests(page, "upload")

    for status, message in _FAILURES:
        _open_upload_tab(page, live_server, stub.pk)
        held = _hold_requests(page, "upload")
        dialog = _open_dialog(page)
        save = _submit_button(dialog)
        _submit_with_file(dialog, save)
        _held_request(page, held, 0).fulfill(status=status, body="Server error")
        alert = dialog.get_by_role("alert")
        expect(alert, f"alert text for a {status}").to_have_text(message)
        expect(
            dialog.locator("[data-request-error]"),
            f"request error not focused after a {status}",
        ).to_be_focused()
        expect(dialog, f"dialog closed after a {status}").to_be_visible()
        expect(
            dialog.get_by_label("Title"), f"title lost after a {status}"
        ).to_have_value("Notes")
        expect(save, f"button not re-enabled after a {status}").to_be_enabled()
        save.click()
        _held_request(page, held, 1).fulfill(status=204)
        expect(
            alert, f"alert still shown after a saved retry of a {status}"
        ).to_have_count(0)
        _release_requests(page, "upload")

    held = _hold_requests(page, "create_item")
    page.goto(f"{live_server.url}/test-panel/framework/stubs")
    page.get_by_role("button", name="Create Item").click()
    dialog = page.locator("#app-modal")
    expect(dialog).to_be_visible()
    dialog.get_by_label("Name").fill("Widget")
    dialog.get_by_role("button", name="Add", exact=True).click()
    _held_request(page, held, 0).fulfill(status=500, body="Server error")
    expect(
        dialog.get_by_role("alert"), "generic error for a dialog with no file field"
    ).to_have_text(_GENERIC_MESSAGE)
    _release_requests(page, "create_item")

    _open_upload_tab(page, live_server, stub.pk)
    held = _hold_requests(page, "upload")
    dialog = _open_dialog(page)
    _submit_without_file(dialog, _submit_button(dialog))
    _held_request(page, held, 0).abort()
    expect(
        dialog.get_by_role("alert"), "generic error for an aborted request"
    ).to_have_text(_GENERIC_MESSAGE)
    _release_requests(page, "upload")

    _open_upload_tab(page, live_server, stub.pk)
    held = _hold_requests(page, "upload")
    dialog = _open_dialog(page)
    dialog.get_by_label("Title").fill("Notes")
    # An event a script dispatches is not a user action, so the page does not
    # reload.
    dialog.locator("form").evaluate("form => htmx.trigger(form, 'submit')")
    _held_request(page, held, 0).fulfill(status=403, body="Forbidden")
    expect(
        dialog.get_by_role("alert"), "generic error for a scripted 403"
    ).to_have_text(_GENERIC_MESSAGE)
    expect(
        dialog.get_by_label("Title"), "title lost after a scripted 403"
    ).to_have_value("Notes")
    _release_requests(page, "upload")

    _open_upload_tab(page, live_server, stub.pk)
    held = _hold_requests(page, "upload")
    dialog = _open_dialog(page)
    _submit_without_file(dialog, _submit_button(dialog))
    _held_request(page, held, 0).fulfill(
        status=500,
        content_type="text/html",
        body=(
            '<div hx-swap-oob="beforeend:#toast-region-assertive">'
            "<p>The server is busy.</p></div>"
        ),
    )
    expect(
        page.get_by_text("The server is busy."), "toast from the response not shown"
    ).to_be_attached()
    expect(
        page.get_by_text(_GENERIC_MESSAGE), "request error added beside a toast"
    ).to_have_count(0)
    _release_requests(page, "upload")

    _open_upload_tab(page, live_server, stub.pk)
    dialog = _open_dialog(page)
    page.keyboard.press("Escape")
    expect(dialog, "Escape did not close a clean dialog").to_be_hidden()

    _open_upload_tab(page, live_server, stub.pk)
    dialog = _open_dialog(page)
    attachment = dialog.get_by_label("Attachment")
    attachment.set_input_files(_FILE)
    page.keyboard.press("Escape")
    expect(
        page.get_by_role("dialog", name="Discard changes?"),
        "Escape did not ask before discarding a chosen file",
    ).to_be_visible()
    page.get_by_role("button", name="Keep editing").click()
    expect(dialog, "dialog closed after Keep editing").to_be_visible()
    assert attachment.evaluate("input => input.files[0].name") == "notes.txt", (
        "chosen file lost after Keep editing"
    )

    _open_upload_tab(page, live_server, stub.pk)
    dialog = _open_dialog(page)
    attachment = dialog.get_by_label("Attachment")
    attachment.set_input_files(_FILE)
    attachment.set_input_files([])
    page.keyboard.press("Escape")
    expect(dialog, "Escape did not close after the file was cleared").to_be_hidden()
    expect(
        page.get_by_role("dialog", name="Discard changes?"),
        "Escape asked to discard after the file was cleared",
    ).to_have_count(0)

    _open_upload_tab(page, live_server, stub.pk)
    held = _hold_requests(page, "upload")
    dialog = _open_dialog(page)
    _submit_with_file(dialog, _submit_button(dialog))
    _held_request(page, held, 0).fulfill(status=500, body="Server error")
    alert = dialog.get_by_role("alert")
    expect(alert).to_have_text(_GENERIC_MESSAGE)
    holder = dialog.locator("[data-request-error]")
    assert _computed_colour(alert) == _computed_colour(holder), (
        "dialog alert colour differs from the holder's error colour"
    )
    _release_requests(page, "upload")

    _open_upload_tab(page, live_server, stub.pk)
    held = _hold_requests(page, "upload")
    dialog = _open_dialog(page)
    _submit_without_file(dialog, _submit_button(dialog))
    with page.expect_navigation():
        _held_request(page, held, 0).fulfill(status=404, body="Not found")
    expect(
        page.get_by_text(_GENERIC_MESSAGE), "generic error shown after a 404 reload"
    ).to_have_count(0)
    expect(
        page.get_by_text(_TOO_LARGE_MESSAGE), "too-large error shown after a 404 reload"
    ).to_have_count(0)
    _release_requests(page, "upload")


def test_file_upload_inline_flow(
    page: Page,
    live_server: pytest_django.live_server_helper.LiveServer,
    live_server_site: Site,
    mock_site_context: None,
) -> None:
    """The inline upload form's request handling, each case from a fresh load.

    Proves that Save reads "Uploading..." while a file goes up, "Saving..." with
    no file and after a failed upload is cleared; that 413 and 500 show the
    matching alert and keep the typed title; and that the alert is drawn in the
    holder's error colour.
    """
    stub = make_stub()

    _open_upload_tab(page, live_server, stub.pk)
    held = _hold_requests(page, "upload_inline")
    form = page.locator("#stub-upload-form")
    save = _inline_submit_button(page)
    _submit_with_file(form, save)
    expect(save, "inline Save not disabled while a file uploads").to_be_disabled()
    expect(save, "inline Save text while a file uploads").to_have_text(
        "Uploading…", use_inner_text=True
    )
    _held_request(page, held, 0).fulfill(status=204)
    _release_requests(page, "upload_inline")

    _open_upload_tab(page, live_server, stub.pk)
    held = _hold_requests(page, "upload_inline")
    _submit_without_file(form, save)
    expect(
        save, "inline Save not disabled while saving without a file"
    ).to_be_disabled()
    expect(save, "inline Save text with no file chosen").to_have_text(
        "Saving…", use_inner_text=True
    )
    _held_request(page, held, 0).fulfill(status=204)
    _release_requests(page, "upload_inline")

    _open_upload_tab(page, live_server, stub.pk)
    held = _hold_requests(page, "upload_inline")
    _submit_with_file(form, save)
    expect(save, "inline Save text while a file uploads before failing").to_have_text(
        "Uploading…", use_inner_text=True
    )
    _held_request(page, held, 0).fulfill(status=500)
    expect(save, "inline Save not re-enabled after a failed upload").to_be_enabled()
    form.get_by_label("Attachment").set_input_files([])
    save.click()
    expect(save, "inline Save text after a failed upload is cleared").to_have_text(
        "Saving…", use_inner_text=True
    )
    _held_request(page, held, 1).fulfill(status=204)
    _release_requests(page, "upload_inline")

    for status, message in _FAILURES:
        _open_upload_tab(page, live_server, stub.pk)
        held = _hold_requests(page, "upload_inline")
        _submit_with_file(form, save)
        _held_request(page, held, 0).fulfill(status=status, body="Server error")
        expect(
            form.get_by_role("alert"), f"inline alert text for a {status}"
        ).to_have_text(message)
        expect(
            form.get_by_label("Title"), f"inline title lost after a {status}"
        ).to_have_value("Notes")
        expect(save, f"inline Save not re-enabled after a {status}").to_be_enabled()
        _release_requests(page, "upload_inline")

    _open_upload_tab(page, live_server, stub.pk)
    held = _hold_requests(page, "upload_inline")
    _submit_with_file(form, save)
    _held_request(page, held, 0).fulfill(status=500, body="Server error")
    alert = form.get_by_role("alert")
    expect(alert).to_have_text(_GENERIC_MESSAGE)
    holder = form.locator("[data-request-error]")
    assert _computed_colour(alert) == _computed_colour(holder), (
        "inline alert colour differs from the holder's error colour"
    )
    _release_requests(page, "upload_inline")
