"""The Create Cohort dialog on a phone.

The dialog is a bottom sheet below sm; its Name field and both footer buttons
must be reachable without scrolling, and Cancel must dismiss it. Widening the
window while it is open docks the sidebar behind it, and Escape must still
reach the dialog afterwards.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Locator, Page, expect

from django.urls import reverse

from freedom_ls.organisations.factories import OrganisationFactory

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_PHONE_VIEWPORT = {"width": 390, "height": 844}
# Wide enough that the sidebar docks as a desktop column.
_DESKTOP_VIEWPORT = {"width": 1442, "height": 900}


def _open_create_cohort_on_a_phone(live_server, page: Page, educator_user) -> Locator:
    organisation = OrganisationFactory()
    educator_user.is_superuser = True
    educator_user.save()
    page.set_viewport_size(_PHONE_VIEWPORT)
    path = reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation.slug, "path_string": "cohorts"},
    )
    page.goto(f"{live_server.url}{path}")
    page.get_by_role("button", name="Create Cohort").click()
    dialog = page.locator("#app-modal")
    expect(dialog).to_be_visible()
    return dialog


def test_create_cohort_dialog_shows_its_field_and_buttons_and_cancel_closes_it(
    live_server,
    educator_logged_in_page: Page,
    educator_user,
) -> None:
    dialog = _open_create_cohort_on_a_phone(
        live_server, educator_logged_in_page, educator_user
    )

    expect(dialog.get_by_label("Name")).to_be_in_viewport()
    expect(dialog.get_by_role("button", name="Cancel")).to_be_in_viewport()
    expect(
        dialog.get_by_role("button", name="Create Cohort", exact=True)
    ).to_be_in_viewport()

    dialog.get_by_role("button", name="Cancel").click()

    expect(dialog).to_be_hidden()


def test_escape_closes_the_dialog_after_widening_past_the_sidebar_breakpoint(
    live_server,
    educator_logged_in_page: Page,
    educator_user,
) -> None:
    page = educator_logged_in_page
    dialog = _open_create_cohort_on_a_phone(live_server, page, educator_user)

    page.set_viewport_size(_DESKTOP_VIEWPORT)
    expect(dialog).to_be_visible()
    page.keyboard.press("Escape")

    expect(dialog).to_be_hidden()
    expect(page.locator("dialog[aria-label='Navigation']")).to_be_visible()


def test_escape_on_a_dirty_dialog_after_widening_asks_to_discard(
    live_server,
    educator_logged_in_page: Page,
    educator_user,
) -> None:
    page = educator_logged_in_page
    dialog = _open_create_cohort_on_a_phone(live_server, page, educator_user)
    dialog.get_by_label("Name").fill("Half-typed cohort")

    page.set_viewport_size(_DESKTOP_VIEWPORT)
    expect(dialog).to_be_visible()
    dialog.get_by_label("Name").focus()
    page.keyboard.press("Escape")

    expect(dialog.locator("[data-modal-discard-prompt]")).to_be_visible()
