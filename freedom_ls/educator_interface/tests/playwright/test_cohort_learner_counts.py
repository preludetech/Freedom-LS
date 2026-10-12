"""The cohort page's learner counts follow a membership change made from the
Learners tab, without a page reload."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory

from .helpers import interface_url

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def test_removing_a_member_updates_the_tab_and_header_learner_counts(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
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
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    page.goto(
        interface_url(
            live_server, organisation.slug, f"cohorts/{cohort.pk}/__tabs/learners"
        )
    )
    modal = page.locator("#app-modal")
    main = page.locator("#main-content")
    header_stat = main.locator("dl").filter(has_text="Learners")
    expect(page.get_by_role("link", name="Learners 2", exact=True)).to_be_visible()

    main.get_by_role("row").filter(has_text="Ada").get_by_role(
        "button", name="Remove", exact=True
    ).click()
    modal.get_by_role("button", name="Remove", exact=True).click()

    expect(modal).to_be_hidden()
    expect(page.get_by_role("link", name="Learners 1", exact=True)).to_be_visible()
    expect(header_stat).to_contain_text("1")
