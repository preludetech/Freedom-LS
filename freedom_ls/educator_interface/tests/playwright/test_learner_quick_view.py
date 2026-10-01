"""E2E Playwright tests for the learner drawer opened from the Learners table.

The Django test client coverage of LearnerQuickView's fields lives in
educator_interface/tests/test_quick_views.py. What only a browser shows is
that clicking a learner's name in the table opens the real #quick-view
drawer, that its Open link leads to the learner's own page, that the drawer
keeps one title whichever cell opened it, and that a learnerChanged domain
event naming the shown learner refetches it.
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


def test_the_drawer_title_is_the_learners_name_from_either_cell_and_on_reopen(
    live_server,
    educator_logged_in_page: Page,
    educator_user: User,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    assign_object_role(educator_user, organisation, "organisation_staff")
    LearnerFactory(
        organisation=organisation,
        user=UserFactory(first_name="Ada", last_name="Lovelace"),
    )
    title = page.locator("#quick-view-title")

    page.goto(interface_url(live_server, organisation.slug, "learners"))
    first_name = page.get_by_role("link", name="Ada", exact=True)
    first_name.click()
    expect(page.locator("#quick-view-body")).not_to_have_attribute("aria-busy", "true")
    expect(title).to_have_text("Ada Lovelace")

    page.keyboard.press("Escape")
    expect(page.locator("#quick-view")).to_be_hidden()
    first_name.click()
    expect(page.locator("#quick-view")).to_be_visible()
    expect(title).to_have_text("Ada Lovelace")

    page.get_by_role("link", name="Lovelace", exact=True).click()
    expect(page.locator("#quick-view")).to_be_visible()
    expect(title).to_have_text("Ada Lovelace")


def test_escape_closes_only_the_topmost_dropdown_leaving_the_drawer_open(
    live_server,
    educator_logged_in_page: Page,
    educator_user: User,
) -> None:
    """A dropdown menu opened over the drawer is its own layer: one Esc
    dismisses the dropdown and leaves the drawer open, a second Esc then
    closes the drawer. Reproduces the QA bug where a single Esc closed both."""
    page = educator_logged_in_page
    organisation_a = OrganisationFactory(name="Org A")
    organisation_b = OrganisationFactory(name="Org B")
    assign_object_role(educator_user, organisation_a, "organisation_staff")
    assign_object_role(educator_user, organisation_b, "organisation_staff")
    LearnerFactory(
        organisation=organisation_a,
        user=UserFactory(first_name="Ada", last_name="Lovelace"),
    )

    page.goto(interface_url(live_server, organisation_a.slug, "learners"))
    page.get_by_role("link", name="Ada", exact=True).click()
    expect(page.locator("#quick-view")).to_be_visible()

    switcher_button = page.get_by_role("button", name="Switch organisation")
    switcher_button.click()
    expect(switcher_button).to_have_attribute("aria-expanded", "true")

    page.keyboard.press("Escape")

    expect(switcher_button).to_have_attribute("aria-expanded", "false")
    # The drawer's close transition keeps it visually on screen for a
    # moment after close() runs, so to_be_visible() alone would pass on a
    # closing drawer too. The [open] boolean attribute is removed the
    # instant close() runs, so it is the reliable signal of whether the
    # drawer is still genuinely open.
    expect(page.locator("#quick-view")).to_have_attribute("open", "")

    page.keyboard.press("Escape")

    expect(page.locator("#quick-view")).not_to_have_attribute("open", "")


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
