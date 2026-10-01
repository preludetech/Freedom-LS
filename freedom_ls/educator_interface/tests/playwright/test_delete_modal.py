"""E2E Playwright test for deleting a cohort from its own page through the
native #app-modal.

The response headers are covered by test_cohort_delete_action.py. What only a
browser shows is that the page being left does not refetch its panels for the
cohort that no longer exists.
"""

from __future__ import annotations

import pytest
from guardian.shortcuts import assign_perm
from playwright.sync_api import Page, Response, expect

from freedom_ls.accounts.models import User
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.learner_management.models import Cohort
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role

from .helpers import interface_url

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def test_deleting_a_cohort_from_its_page_makes_no_failing_requests(
    live_server,
    educator_logged_in_page: Page,
    educator_user: User,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    cohort = CohortFactory(organisation=organisation, name="Doomed Cohort")
    cohort_pk = cohort.pk
    assign_object_role(educator_user, organisation, "organisation_staff")
    assign_perm("freedom_ls_learner_management.delete_cohort", educator_user, cohort)
    failed: list[str] = []

    def record_failure(response: Response) -> None:
        if response.status >= 400:
            failed.append(f"{response.status} {response.url}")

    page.goto(interface_url(live_server, organisation.slug, f"cohorts/{cohort.pk}"))
    page.on("response", record_failure)

    page.get_by_role("button", name="Delete", exact=True).click()
    # Scoped: the trigger with the same name sits behind the dialog.
    page.locator("#app-modal").get_by_role("button", name="Delete", exact=True).click()

    expect(page.locator("#app-modal")).to_be_hidden()
    expect(page).to_have_url(interface_url(live_server, organisation.slug, "cohorts"))
    page.wait_for_load_state("networkidle")
    assert not Cohort.objects.filter(pk=cohort_pk).exists()
    assert failed == []
