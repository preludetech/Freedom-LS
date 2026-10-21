"""E2E Playwright flow for the Members list: add a user as a cohort admin on
two cohorts, change their cohorts and remove the role, all through the native
#app-modal. The refusals, headers and outcomes are covered by test_actions.py;
what only a browser shows is the Alpine cohort checklist and role chooser, the
dialog steps replacing one another inside the open modal, and the list behind
it refreshing after each change.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, Response, expect

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.factories import CohortFactory, LearnerFactory
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


def test_add_change_and_remove_a_cohort_admin_refreshes_the_list(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    CohortFactory(organisation=organisation, name="Alpha Cohort")
    CohortFactory(organisation=organisation, name="Beta Cohort")
    UserFactory(email="existing@example.com", first_name="Erin", last_name="Existing")
    failed: list[str] = []

    def record_failure(response: Response) -> None:
        if response.status >= 400:
            failed.append(f"{response.status} {response.url}")

    page.goto(interface_url(live_server, organisation.slug, "members"))
    page.on("response", record_failure)
    modal = page.locator("#app-modal")
    main = page.locator("#main-content")

    main.get_by_role("button", name="Add member", exact=True).first.click()
    modal.get_by_label("Email address").fill("existing@example.com")
    modal.get_by_role("button", name="Look up", exact=True).click()
    expect(modal.get_by_text("Existing account")).to_be_visible()

    modal.get_by_text("Cohort admin", exact=True).click()
    modal.get_by_label("Alpha Cohort").check()
    modal.get_by_label("Beta Cohort").check()
    expect(modal.get_by_text("2 selected")).to_be_visible()
    modal.get_by_role("button", name="Add member", exact=True).click()

    expect(modal.get_by_text("Scope: Alpha Cohort and Beta Cohort")).to_be_visible()
    modal.get_by_role("button", name="Add member", exact=True).click()

    expect(modal).to_be_hidden()
    row = main.get_by_role("row").filter(has_text="Erin Existing")
    expect(row.get_by_text("Cohort admin")).to_be_visible()
    expect(row.get_by_text("Alpha Cohort")).to_be_visible()
    expect(row.get_by_text("Beta Cohort")).to_be_visible()

    row.get_by_role("button", name="Change cohorts", exact=True).click()
    modal.get_by_label("Beta Cohort").uncheck()
    modal.get_by_role("button", name="Change cohorts", exact=True).click()
    expect(modal.get_by_text("Removes: Beta Cohort")).to_be_visible()
    modal.get_by_role("button", name="Change cohorts", exact=True).click()

    expect(modal).to_be_hidden()
    expect(row.get_by_text("Alpha Cohort")).to_be_visible()
    expect(row.get_by_text("Beta Cohort")).to_have_count(0)

    row.get_by_role("button", name="Remove", exact=True).click()
    expect(modal.get_by_text("They lose")).to_be_visible()
    modal.get_by_role("button", name="Remove", exact=True).click()

    expect(modal).to_be_hidden()
    expect(main.get_by_text("Erin Existing")).to_have_count(0)
    page.wait_for_load_state("networkidle")
    assert failed == []

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(page)

    page.set_viewport_size(QA_VIEWPORTS[0])
    page.goto(interface_url(live_server, organisation.slug, "members"))
    expect(main.locator("[data-card-primary-line]").first).to_be_visible()


def test_clear_filters_after_a_no_match_search_empties_the_search_box(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    """The search box survives the region swap, so the server's empty value
    has to reach it; otherwise the box contradicts the restored list."""
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    page.goto(interface_url(live_server, organisation.slug, "members"))
    main = page.locator("#main-content")
    search = main.locator("#members-q")
    search.fill("zzz")
    # The empty state renders once for the table and once for the card list.
    expect(main.get_by_text("No members match.").first).to_be_visible()

    main.get_by_role("link", name="Clear filters", exact=True).first.click()

    expect(main.get_by_text("No members match.")).to_have_count(0)
    expect(search).to_have_value("")


def test_phone_row_actions_and_toolbar_controls_meet_the_touch_target(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    cohort = CohortFactory(organisation=organisation, name="Alpha Cohort")
    viewer = UserFactory(
        email="viewer@example.com", first_name="Vee", last_name="Viewer"
    )
    assign_role(grantor, viewer, "cohort_viewer", cohort)
    page.set_viewport_size(QA_VIEWPORTS[0])
    page.goto(interface_url(live_server, organisation.slug, "members"))
    main = page.locator("#main-content")
    card = main.locator("li").filter(has_text="Vee Viewer")
    expect(card).to_be_visible()

    for control in (
        card.get_by_role("button", name="Remove", exact=True),
        card.get_by_role("button", name="Suspend", exact=True),
        main.get_by_role("button", name="Filter"),
        main.get_by_role("button", name="Sort"),
    ):
        box = control.bounding_box()
        assert box is not None
        assert box["height"] >= 44, f"{control} is {box['height']}px high"
