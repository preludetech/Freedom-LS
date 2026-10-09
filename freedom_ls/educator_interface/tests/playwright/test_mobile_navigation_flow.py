"""Browser flow for the educator interface on a phone and across the sidebar
breakpoint.

Below ``lg`` the sidebar is a modal ``<dialog>`` opened with ``showModal()``;
from ``lg`` up it docks as a column. The Django test client never runs the
sheet controller, and ``<dialog>`` modality, focus and session history are
browser state.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.factories import CohortFactory, LearnerFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role
from freedom_ls.tests.playwright_helpers import QA_VIEWPORTS

from .helpers import interface_url

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_PHONE = QA_VIEWPORTS[0]
# Wide enough that the sidebar docks as a desktop column.
_DESKTOP = {"width": 1442, "height": 900}


def test_educator_navigates_and_creates_a_cohort_on_a_phone(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation_a = OrganisationFactory(name="Org A")
    organisation_b = OrganisationFactory(name="Org B")
    CohortFactory(organisation=organisation_a, name="Alpha Cohort")
    CohortFactory(organisation=organisation_b, name="Beta Cohort")
    assign_object_role(educator_user, organisation_a, "organisation_admin")
    assign_object_role(educator_user, organisation_b, "organisation_admin")
    LearnerFactory(user=UserFactory(), organisation=organisation_a)
    learners_url = interface_url(live_server, organisation_a.slug, "learners")
    cohorts_url = interface_url(live_server, organisation_a.slug, "cohorts")
    page.set_viewport_size(_PHONE)
    sheet = page.locator("dialog[aria-label='Navigation']")
    filter_sheet = page.locator("dialog[aria-label='Filter and sort']")
    toggle = page.get_by_role("button", name="Open navigation panel")
    alpha_link = page.get_by_role("link", name="Alpha Cohort", exact=True)

    # The sidebar and the table's filter sheet are two nested sidePanel
    # components; the nav button must open its own dialog, not the nearer one.
    page.goto(learners_url)
    expect(sheet).to_be_hidden()
    expect(filter_sheet).to_be_hidden()
    toggle.click()
    expect(sheet).to_be_visible()
    expect(filter_sheet).to_be_hidden()
    expect(sheet.locator("#sidebar-nav")).to_be_visible()

    body = sheet.locator(".side-panel-body")
    expect(body).to_have_css("border-top-left-radius", "16px")
    expect(body).to_have_css("border-top-right-radius", "16px")

    # Closing returns focus to the toggle that opened the sheet.
    sheet.get_by_role("button", name="Close navigation").click()
    expect(sheet).to_be_hidden()
    expect(toggle).to_be_focused()

    # The slide is a CSS transition that reduced motion switches off.
    page.emulate_media(reduced_motion="reduce")
    toggle.click()
    expect(sheet).to_be_visible()
    expect(sheet).to_have_css("transition-duration", "0s")

    # A section link loads over htmx (a surviving window marker proves no
    # document load), dismisses the sheet and moves focus into the content:
    # the toggle was swapped out with the content it sat in.
    page.evaluate("window.__noReloadMarker = true")
    sheet.get_by_role("link", name="Cohorts").click()
    expect(page).to_have_url(cohorts_url)
    expect(alpha_link).to_be_visible()
    expect(sheet).to_be_hidden()
    expect(page.locator("#main-content")).to_be_focused()
    assert page.evaluate("window.__noReloadMarker === true")
    page.go_back()
    expect(page).to_have_url(learners_url)

    # Switching organisation from the sheet closes it, and Back restores the
    # organisation switched away from with its content, not a mismatch.
    page.goto(cohorts_url)
    toggle.click()
    expect(sheet).to_be_visible()
    page.get_by_role("button", name="Switch organisation").click()
    page.get_by_role("menuitemradio", name="Org B").click()
    expect(page).to_have_url(interface_url(live_server, organisation_b.slug, "cohorts"))
    expect(sheet).to_be_hidden()
    expect(page.get_by_role("link", name="Beta Cohort", exact=True)).to_be_visible()
    page.go_back()
    expect(page).to_have_url(cohorts_url)
    expect(sheet).to_be_hidden()
    expect(page.locator("#organisation-switcher")).to_contain_text("Org A")
    expect(alpha_link).to_be_visible()

    # Widening past the sidebar breakpoint with the sheet open docks it.
    toggle.click()
    expect(sheet).to_be_visible()
    expect(page.locator("dialog[aria-label='Navigation']:modal")).to_have_count(1)
    page.set_viewport_size(_DESKTOP)
    # Docking closes the modal and re-shows the dialog without modality, so
    # the sheet is briefly hidden in between: settle on non-modal first.
    expect(page.locator("dialog[aria-label='Navigation']:modal")).to_have_count(0)
    expect(sheet).to_be_visible()
    sidebar_box = sheet.bounding_box()
    main_box = page.locator("#main-content").bounding_box()
    assert sidebar_box is not None
    assert main_box is not None
    assert sidebar_box["width"] >= 200
    assert main_box["width"] >= 800
    assert main_box["x"] >= sidebar_box["x"] + sidebar_box["width"]

    # The create-cohort bottom sheet shows its field and both buttons without
    # scrolling, and Cancel dismisses it.
    page.set_viewport_size(_PHONE)
    page.goto(cohorts_url)
    expect(sheet).to_be_hidden()
    dialog = page.locator("#app-modal")
    create_trigger = page.get_by_role("button", name="Create Cohort")
    create_trigger.click()
    expect(dialog).to_be_visible()
    name_field = dialog.get_by_label("Name")
    cancel = dialog.get_by_role("button", name="Cancel")
    expect(name_field).to_be_in_viewport()
    expect(cancel).to_be_in_viewport()
    expect(
        dialog.get_by_role("button", name="Create Cohort", exact=True)
    ).to_be_in_viewport()

    # The sheet slides out over its closing transition, so its form stays
    # until the next open replaces it rather than sending an empty sheet down
    # the screen.
    name_field.fill("Half-typed cohort")
    cancel.click()
    expect(page.locator("#app-modal-body form")).to_have_count(1)
    expect(dialog).to_be_hidden()
    create_trigger.click()
    expect(dialog).to_be_visible()
    expect(name_field).to_have_value("")

    # Escape still reaches the dialog once widening docks the sidebar behind it.
    page.set_viewport_size(_DESKTOP)
    expect(dialog).to_be_visible()
    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()
    expect(sheet).to_be_visible()

    # A dirty dialog asks before discarding.
    page.set_viewport_size(_PHONE)
    page.goto(cohorts_url)
    expect(sheet).to_be_hidden()
    create_trigger.click()
    expect(dialog).to_be_visible()
    name_field.fill("Half-typed cohort")
    page.set_viewport_size(_DESKTOP)
    expect(dialog).to_be_visible()
    name_field.focus()
    page.keyboard.press("Escape")
    discard = page.get_by_role("dialog", name="Discard changes?")
    expect(discard).to_be_visible()
    discard.get_by_role("button", name="Discard").click()
    expect(dialog).to_be_hidden()

    # On a fresh desktop page the first Tab reaches the site header.
    page.goto(cohorts_url)
    expect(sheet).to_be_visible()
    assert page.evaluate("document.activeElement === document.body")
    page.keyboard.press("Tab")
    assert page.evaluate(
        "document.querySelector('header.header').contains(document.activeElement)"
    )
