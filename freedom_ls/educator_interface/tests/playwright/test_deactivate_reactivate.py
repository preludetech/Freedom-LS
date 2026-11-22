"""E2E Playwright flow for a cohort's Settings tab.

The state change and headers are covered by test_actions.py. The flow proves
what only a browser shows:

- the confirmation dialog opens from the keyboard with Cancel focused, and
  Esc closes it and returns focus to the trigger;
- deactivating then reactivating through the native #app-modal re-renders
  the page in full, header badge and state button included, with no failing
  request along the way;
- saving a rename updates the title, leaves no modal open and keeps focus on
  the name field.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Locator, Page, Response, expect

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.learner_management.factories import CohortFactory, LearnerFactory
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role

from .helpers import interface_url

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_MAX_TABS = 60


def _tab_to(page: Page, target: Locator) -> None:
    """Presses Tab until ``target`` holds focus, failing if it never does."""
    for _ in range(_MAX_TABS):
        page.keyboard.press("Tab")
        if target.evaluate("element => element === document.activeElement"):
            return
    pytest.fail("Tab never reached the target control")


def test_cohort_settings_tab_flow(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    page.set_viewport_size({"width": 1440, "height": 900})
    organisation = OrganisationFactory(name="Org A")
    cohort = CohortFactory(organisation=organisation, name="Evening group")
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    assign_object_role(educator_user, cohort, "cohort_admin")
    failed: list[str] = []

    def record_failure(response: Response) -> None:
        if response.status >= 400:
            failed.append(f"{response.status} {response.url}")

    page.goto(
        interface_url(
            live_server, organisation.slug, f"cohorts/{cohort.pk}/__tabs/settings"
        )
    )
    page.on("response", record_failure)
    modal = page.locator("#app-modal")
    main = page.locator("#main-content")

    # Keyboard.
    trigger = main.get_by_role("button", name="Deactivate", exact=True).first
    expect(trigger).to_be_visible()
    _tab_to(page, trigger)
    page.keyboard.press("Enter")
    expect(modal).to_be_visible()
    expect(
        modal.get_by_role("button", name="Cancel", exact=True),
        "Cancel not focused when the dialog opened by keyboard",
    ).to_be_focused()
    page.keyboard.press("Escape")
    expect(modal).to_be_hidden()
    expect(trigger, "focus not returned to Deactivate after Esc").to_be_focused()

    main.get_by_role("button", name="Deactivate", exact=True).first.click()
    modal.get_by_role("button", name="Deactivate", exact=True).click()

    expect(modal).to_be_hidden()
    # The header refreshes on the cohort-changed event and shows the badge.
    expect(
        page.locator("#instance-header").get_by_text("Inactive", exact=True)
    ).to_be_visible()
    expect(
        main.get_by_role("button", name="Reactivate", exact=True).first
    ).to_be_visible()

    main.get_by_role("button", name="Reactivate", exact=True).first.click()
    modal.get_by_role("button", name="Reactivate", exact=True).click()

    expect(modal).to_be_hidden()
    expect(
        page.locator("#instance-header").get_by_text("Inactive", exact=True)
    ).to_have_count(0)
    expect(
        main.get_by_role("button", name="Deactivate", exact=True).first
    ).to_be_visible()
    page.wait_for_load_state("networkidle")
    assert failed == []

    # Rename.
    name_panel = page.locator("section[data-panel='name']")
    name_panel.get_by_label("Name").fill("New Name")
    name_panel.get_by_role("button", name="Save", exact=True).click()

    expect(page.locator("#instance-title")).to_have_text("New Name")
    expect(modal).to_be_hidden()
    expect(name_panel.get_by_label("Name")).to_have_value("New Name")
    expect(
        name_panel.get_by_label("Name"), "focus left the name field after saving"
    ).to_be_focused()
    assert page.evaluate(
        "document.activeElement !== null && document.activeElement !== document.body"
    ), "focus dropped to <body> after saving the rename"
    assert failed == [], "a request failed during the rename"
