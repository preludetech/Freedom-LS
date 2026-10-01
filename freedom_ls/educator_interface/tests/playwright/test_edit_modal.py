"""E2E Playwright test for editing an instance through the native #app-modal.

The Django test client coverage of EditAction's response contract lives in
educator_interface/tests/test_cohort_delete_action.py and
panel_framework/tests/test_panel_actions.py. What only a browser shows is
that the modal actually closes and the page heading updates in place.
"""

from __future__ import annotations

import pytest
from guardian.shortcuts import assign_perm
from playwright.sync_api import Page, expect

from freedom_ls.accounts.models import User
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role

from .helpers import interface_url

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def test_editing_a_cohorts_name_closes_the_modal_and_updates_the_title(
    live_server,
    educator_logged_in_page: Page,
    educator_user: User,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    cohort = CohortFactory(organisation=organisation, name="Old Name")
    assign_object_role(educator_user, organisation, "organisation_staff")
    assign_perm("freedom_ls_learner_management.change_cohort", educator_user, cohort)

    page.goto(interface_url(live_server, organisation.slug, f"cohorts/{cohort.pk}"))

    page.get_by_role("button", name="Edit").click()
    # Scoped: the dialog's own aria-labelledby also matches get_by_label.
    page.locator("#app-modal-body").get_by_label("Name").fill("New Name")
    page.get_by_role("button", name="Save", exact=True).click()

    expect(page.locator("#app-modal")).to_be_hidden()
    expect(page.locator("#instance-title")).to_have_text("New Name")


def test_editing_a_cohorts_name_updates_the_breadcrumb_trail(
    live_server,
    educator_logged_in_page: Page,
    educator_user: User,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    cohort = CohortFactory(organisation=organisation, name="Old Name")
    assign_object_role(educator_user, organisation, "organisation_staff")
    assign_perm("freedom_ls_learner_management.change_cohort", educator_user, cohort)

    page.goto(interface_url(live_server, organisation.slug, f"cohorts/{cohort.pk}"))

    page.get_by_role("button", name="Edit").click()
    page.locator("#app-modal-body").get_by_label("Name").fill("New Name")
    page.get_by_role("button", name="Save", exact=True).click()

    expect(page.locator("#app-modal")).to_be_hidden()
    expect(page.locator("#breadcrumbs")).to_contain_text("New Name")
    expect(page.locator("#breadcrumbs")).not_to_contain_text("Old Name")
