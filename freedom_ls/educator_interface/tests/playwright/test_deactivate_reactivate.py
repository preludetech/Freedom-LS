"""E2E Playwright test for deactivating and reactivating a cohort from its
Settings tab through the native #app-modal.

The state change and headers are covered by test_actions.py. What only a
browser shows is that the page re-renders in full, header badge and state
button included, with no failing request along the way.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, Response, expect

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.learner_management.factories import CohortFactory, LearnerFactory
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory

from .helpers import interface_url

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def test_deactivating_then_reactivating_a_cohort_from_its_settings_tab(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    cohort = CohortFactory(organisation=organisation, name="Evening group")
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
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

    main.get_by_role("button", name="Deactivate", exact=True).first.click()
    modal.get_by_role("button", name="Deactivate", exact=True).click()

    expect(modal).to_be_hidden()
    expect(main.get_by_text("Inactive", exact=True).first).to_be_visible()
    expect(
        main.get_by_role("button", name="Reactivate", exact=True).first
    ).to_be_visible()

    main.get_by_role("button", name="Reactivate", exact=True).first.click()
    modal.get_by_role("button", name="Reactivate", exact=True).click()

    expect(modal).to_be_hidden()
    expect(main.get_by_text("Active", exact=True).first).to_be_visible()
    expect(
        main.get_by_role("button", name="Deactivate", exact=True).first
    ).to_be_visible()
    page.wait_for_load_state("networkidle")
    assert failed == []
