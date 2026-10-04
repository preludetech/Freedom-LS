"""The Create Cohort dialog on a phone.

The dialog is a bottom sheet below sm; its Name field and both footer buttons
must be reachable without scrolling, and Cancel must dismiss it.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from django.urls import reverse

from freedom_ls.organisations.factories import OrganisationFactory

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_PHONE_VIEWPORT = {"width": 390, "height": 844}


def test_create_cohort_dialog_shows_its_field_and_buttons_and_cancel_closes_it(
    live_server,
    educator_logged_in_page: Page,
    educator_user,
) -> None:
    organisation = OrganisationFactory()
    educator_user.is_superuser = True
    educator_user.save()
    page = educator_logged_in_page
    page.set_viewport_size(_PHONE_VIEWPORT)
    path = reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation.slug, "path_string": "cohorts"},
    )
    page.goto(f"{live_server.url}{path}")

    page.get_by_role("button", name="Create Cohort").click()

    dialog = page.locator("#app-modal")
    expect(dialog).to_be_visible()
    expect(dialog.get_by_label("Name")).to_be_in_viewport()
    expect(dialog.get_by_role("button", name="Cancel")).to_be_in_viewport()
    expect(dialog.get_by_role("button", name="Save", exact=True)).to_be_in_viewport()

    dialog.get_by_role("button", name="Cancel").click()

    expect(dialog).to_be_hidden()
