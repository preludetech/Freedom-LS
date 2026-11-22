"""The cohort Learners tab after a member is removed through the confirmation
dialog.

The flow proves:

- the Learners tab count follows the removal without a page reload;
- focus is not left on ``<body>``: the table refresh removes the trigger the
  closing dialog had just refocused.
"""

from __future__ import annotations

import re

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


def test_cohort_learners_tab_flow(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    page.set_viewport_size({"width": 1440, "height": 900})
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
    # The header carries no stats: the Learners tab's count is the figure.
    expect(page.get_by_role("link", name="Learners 2", exact=True)).to_be_visible()

    main.get_by_role("row").filter(has_text="Ada").get_by_role(
        "button", name=re.compile(r"^Remove Ada ")
    ).click()
    modal.get_by_role("button", name="Remove", exact=True).click()

    expect(modal).to_be_hidden()
    expect(page.get_by_role("link", name="Learners 1", exact=True)).to_be_visible()
    assert page.evaluate(
        "document.activeElement !== null && document.activeElement !== document.body"
    ), "focus dropped to <body> after confirming the row removal"
