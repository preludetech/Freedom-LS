"""Browser flows driven only by the keyboard: opening and dismissing the
learner quick view and a confirmation dialog.

Where focus lands, where it returns and whether a ``<dialog>`` is modal are
browser state the Django test client never runs.
"""

from __future__ import annotations

import re
from typing import cast

import pytest
from playwright.sync_api import Locator, Page, expect

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.utils import assign_object_role
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


def _organisation_with_learner(educator_user: AbstractBaseUser) -> Organisation:
    organisation = cast(Organisation, OrganisationFactory(name="Org A"))
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


def test_quick_view_leaves_the_page_usable_on_a_phone(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    """A quick view is a look, not a decision: it never blocks the page, so
    the next row can be tapped behind the sheet."""
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
    assert quick_view.evaluate("dialog => dialog.matches(':modal')") is False
    expect(page.locator("dialog:modal")).to_have_count(0)
    # The list's search box, above the sheet, still takes a tap.
    search = page.locator("#main-content input[type='search']").first
    search.click()
    expect(search).to_be_focused()
    expect(quick_view).to_be_visible()


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


def _admin_of(educator_user: AbstractBaseUser, organisation: object) -> None:
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)


def _focus_is_on_the_page(page: Page) -> bool:
    return bool(
        page.evaluate(
            "document.activeElement !== null && document.activeElement !== document.body"
        )
    )


def test_confirming_a_row_removal_does_not_leave_focus_on_the_body(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    """Confirming "Remove" on a table row refreshes the table, which removes
    the trigger the closing dialog had just refocused, so focus used to drop
    to <body>."""
    page = educator_logged_in_page
    page.set_viewport_size(_DESKTOP)
    organisation = OrganisationFactory(name="Org A")
    cohort = CohortFactory(organisation=organisation, name="Evening group")
    for first_name in ("Ada", "Grace"):
        CohortMembershipFactory(
            cohort=cohort,
            learner=LearnerFactory(
                organisation=organisation,
                user=UserFactory(first_name=first_name, last_name="Lovelace"),
            ),
        )
    _admin_of(educator_user, organisation)
    page.goto(
        interface_url(
            live_server, organisation.slug, f"cohorts/{cohort.pk}/__tabs/learners"
        )
    )
    modal = page.locator("#app-modal")
    main = page.locator("#main-content")

    main.get_by_role("row").filter(has_text="Ada").get_by_role(
        "button", name=re.compile(r"^Remove Ada ")
    ).click()
    modal.get_by_role("button", name="Remove", exact=True).click()

    expect(modal).to_be_hidden()
    expect(main.get_by_role("row").filter(has_text="Ada")).to_have_count(0)
    assert _focus_is_on_the_page(page)


def test_reactivating_a_registration_from_the_overview_card_keeps_focus_on_the_page(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    """The confirm fires two events and three Overview regions refresh at
    once; the Registrations card re-renders its own trigger, so focus has to
    be recovered for that swap whatever order the three settle in."""
    page = educator_logged_in_page
    page.set_viewport_size(_DESKTOP)
    organisation = OrganisationFactory(name="Org A")
    learner = LearnerFactory(
        organisation=organisation, user__first_name="Ada", user__last_name="Lovelace"
    )
    LearnerCourseRegistrationFactory(
        learner=learner, course__title="Orbits", is_active=False
    )
    _admin_of(educator_user, organisation)
    page.goto(interface_url(live_server, organisation.slug, f"learners/{learner.pk}"))
    modal = page.locator("#app-modal")
    row = page.get_by_test_id("registration-row").filter(has_text="Orbits")

    row.get_by_role("button", name="Reactivate", exact=True).click()
    modal.get_by_role("button", name="Reactivate", exact=True).click()

    expect(modal).to_be_hidden()
    expect(row.get_by_text("Active", exact=True)).to_be_visible()
    assert _focus_is_on_the_page(page)


def test_saving_a_cohort_edit_keeps_focus_on_the_page(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    page.set_viewport_size(_DESKTOP)
    organisation = OrganisationFactory(name="Org A")
    cohort = CohortFactory(organisation=organisation, name="Old Name")
    _admin_of(educator_user, organisation)
    assign_object_role(educator_user, cohort, "cohort_admin")
    page.goto(
        interface_url(
            live_server, organisation.slug, f"cohorts/{cohort.pk}/__tabs/settings"
        )
    )
    settings = page.locator("section[data-panel='settings']")

    settings.get_by_label("Name").fill("New Name")
    settings.get_by_role("button", name="Save", exact=True).click()

    expect(page.locator("#instance-title")).to_have_text("New Name")
    expect(page.locator("#app-modal")).to_be_hidden()
    expect(settings.get_by_label("Name")).to_have_value("New Name")
    expect(settings.get_by_label("Name")).to_be_focused()
    assert _focus_is_on_the_page(page)
