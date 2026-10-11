"""E2E Playwright flow for the Learners list: Add learners through the native
#app-modal. The outcomes and headers are covered by test_actions.py; what only
a browser shows is that the results replace the form inside the open modal
and that the list behind it refreshes to show the new learner.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, Response, expect

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

from .helpers import interface_url

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def test_add_learners_reports_each_address_and_refreshes_the_list(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    UserFactory(email="existing@example.com")
    removed = LearnerFactory(organisation=organisation, is_active=False)
    failed: list[str] = []

    def record_failure(response: Response) -> None:
        if response.status >= 400:
            failed.append(f"{response.status} {response.url}")

    page.goto(interface_url(live_server, organisation.slug, "learners"))
    page.on("response", record_failure)
    modal = page.locator("#app-modal")
    main = page.locator("#main-content")

    main.get_by_role("button", name="Add learners", exact=True).first.click()
    modal.get_by_label("Entries").fill(
        f"existing@example.com\n{removed.user.email}\nbrand.new@example.com, Bea, Newman"
    )
    modal.get_by_role("button", name="Add learners", exact=True).click()

    results = modal.get_by_test_id("add-learners-results")
    expect(results.get_by_text("Joined the organisation")).to_be_visible()
    expect(results.get_by_text("Reactivated")).to_be_visible()
    expect(results.get_by_text("Account created and setup email sent")).to_be_visible()

    modal.get_by_text("Close", exact=True).click()

    expect(modal).to_be_hidden()
    expect(main.get_by_text("Bea Newman").first).to_be_visible()
    expect(main.get_by_text("Pending").first).to_be_visible()
    page.wait_for_load_state("networkidle")
    assert failed == []

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(page)
