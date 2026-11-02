"""Browser flows driven only by the keyboard: opening and dismissing the
learner quick view and a confirmation dialog.

Where focus lands, where it returns and whether a ``<dialog>`` is modal are
browser state the Django test client never runs.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Locator, Page, expect

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.learner_management.factories import CohortFactory, LearnerFactory
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.tests.playwright_helpers import QA_VIEWPORTS

from .helpers import interface_url

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_DESKTOP = {"width": 1440, "height": 900}
_PHONE = QA_VIEWPORTS[0]
_MAX_TABS = 60


def _tab_to(page: Page, target: Locator) -> None:
    """Presses Tab until ``target`` holds focus, failing if it never does."""
    for _ in range(_MAX_TABS):
        page.keyboard.press("Tab")
        if target.evaluate("element => element === document.activeElement"):
            return
    pytest.fail("Tab never reached the target control")


def _organisation_with_learner(educator_user: AbstractBaseUser):
    organisation = OrganisationFactory(name="Org A")
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    LearnerFactory(
        organisation=organisation,
        user__first_name="Kai",
        user__last_name="Ngata",
    )
    return organisation


def test_quick_view_opens_with_the_keyboard_and_escape_returns_focus_to_the_trigger(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    page.set_viewport_size(_DESKTOP)
    organisation = _organisation_with_learner(educator_user)
    page.goto(interface_url(live_server, organisation.slug, "learners"))
    trigger = page.locator("#learners-table").get_by_role(
        "link", name="Quick view: Kai Ngata"
    )
    expect(trigger).to_be_visible()

    _tab_to(page, trigger)
    page.keyboard.press("Enter")

    quick_view = page.locator("#quick-view")
    expect(quick_view).to_be_visible()
    expect(quick_view.locator(":focus")).to_have_count(1)

    page.keyboard.press("Escape")

    expect(quick_view).to_be_hidden()
    expect(trigger).to_be_focused()


def test_quick_view_is_modal_on_a_phone(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    page.set_viewport_size(_PHONE)
    organisation = _organisation_with_learner(educator_user)
    page.goto(interface_url(live_server, organisation.slug, "learners"))
    trigger = page.locator("#learners-table").get_by_role(
        "link", name="Quick view: Kai Ngata"
    )

    trigger.click()

    quick_view = page.locator("#quick-view")
    expect(quick_view).to_be_visible()
    assert quick_view.evaluate("dialog => dialog.matches(':modal')") is True


def test_confirmation_dialog_opens_with_the_keyboard_and_escape_returns_focus_to_the_trigger(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    page.set_viewport_size(_DESKTOP)
    organisation = OrganisationFactory(name="Org A")
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    cohort = CohortFactory(organisation=organisation, name="Evening group")
    page.goto(
        interface_url(
            live_server, organisation.slug, f"cohorts/{cohort.pk}/__tabs/settings"
        )
    )
    trigger = (
        page.locator("#main-content")
        .get_by_role("button", name="Deactivate", exact=True)
        .first
    )
    expect(trigger).to_be_visible()

    _tab_to(page, trigger)
    page.keyboard.press("Enter")

    modal = page.locator("#app-modal")
    expect(modal).to_be_visible()
    expect(modal.get_by_role("button", name="Cancel", exact=True)).to_be_focused()

    page.keyboard.press("Escape")

    expect(modal).to_be_hidden()
    expect(trigger).to_be_focused()
