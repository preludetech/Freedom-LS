"""E2E Playwright tests for the learner drawer opened from the Learners table.

The Django test client coverage of LearnerQuickView's fields lives in
educator_interface/tests/test_quick_views.py. What only a browser shows is
that clicking a learner's name in the table opens the real #quick-view
drawer, that its Open link leads to the learner's own page, and that a
learnerChanged domain event naming the shown learner refetches it.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.learner_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role

from .helpers import interface_url

pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def test_clicking_a_learner_opens_the_drawer_and_open_leads_to_the_learner_page(
    live_server,
    educator_logged_in_page: Page,
    educator_user: User,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    assign_object_role(educator_user, organisation, "organisation_staff")
    cohort = CohortFactory(organisation=organisation, name="Year 9 Maths")
    learner = LearnerFactory(
        organisation=organisation,
        user=UserFactory(
            first_name="Ada", last_name="Lovelace", email="ada@example.com"
        ),
    )
    CohortMembershipFactory(learner=learner, cohort=cohort)

    page.goto(interface_url(live_server, organisation.slug, "learners"))
    page.get_by_role("link", name="Ada", exact=True).click()

    expect(page.locator("#quick-view")).to_be_visible()
    expect(page.locator("#quick-view-body")).to_contain_text("ada@example.com")
    expect(page.locator("#quick-view-body")).to_contain_text("Year 9 Maths")

    page.locator("#quick-view-open").click()

    expect(page).to_have_url(
        interface_url(live_server, organisation.slug, f"learners/{learner.pk}")
    )


def test_a_learner_changed_event_naming_the_shown_learner_refetches_it(
    live_server,
    educator_logged_in_page: Page,
    educator_user: User,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    assign_object_role(educator_user, organisation, "organisation_staff")
    learner = LearnerFactory(
        organisation=organisation,
        user=UserFactory(
            first_name="Ada", last_name="Lovelace", email="ada@example.com"
        ),
    )

    page.goto(interface_url(live_server, organisation.slug, "learners"))
    page.get_by_role("link", name="Ada", exact=True).click()
    expect(page.locator("#quick-view")).to_be_visible()

    with (
        pytest.raises(PlaywrightTimeoutError),
        page.expect_request(lambda request: "__quick-view" in request.url, timeout=500),
    ):
        page.evaluate(
            "document.body.dispatchEvent(new CustomEvent('learnerChanged', "
            "{detail: {ids: ['not-this-learner']}}))"
        )

    with page.expect_request(lambda request: "__quick-view" in request.url):
        page.evaluate(
            "(id) => document.body.dispatchEvent(new CustomEvent('learnerChanged', "
            "{detail: {ids: [id]}}))",
            str(learner.pk),
        )
