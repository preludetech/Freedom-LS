"""Keyboard-driven focus on the learner page.

Where focus lands after a confirmed action is browser state the Django test
client never runs.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.learner_management.factories import (
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory

from .helpers import interface_url

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_DESKTOP = {"width": 1440, "height": 900}


def _admin_of(educator_user: AbstractBaseUser, organisation: object) -> None:
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)


def _focus_is_on_the_page(page: Page) -> bool:
    return bool(
        page.evaluate(
            "document.activeElement !== null && document.activeElement !== document.body"
        )
    )


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
    assert _focus_is_on_the_page(page), "focus dropped to <body> after reactivating"
