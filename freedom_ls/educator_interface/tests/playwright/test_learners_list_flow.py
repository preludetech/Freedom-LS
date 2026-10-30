"""E2E Playwright flow for the Learners list: Add learners through the native
#app-modal. The outcomes and headers are covered by test_actions.py; what only
a browser shows is that the results replace the form inside the open modal
and that the list behind it refreshes to show the new learner.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser, Page, Response, Route, expect

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.factories import CohortFactory, LearnerFactory
from freedom_ls.learner_management.models import CohortMembership, Learner
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


def test_bulk_add_then_remove_cohort_for_every_matching_learner(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    cohort = CohortFactory(organisation=organisation, name="Evening group")
    matching = 13
    for _ in range(matching):
        LearnerFactory(organisation=organisation, user__first_name="Pickme")
    for _ in range(3):
        LearnerFactory(organisation=organisation, user__first_name="Other")
    page.goto(
        f"{interface_url(live_server, organisation.slug, 'learners')}?learners-q=Pickme"
    )
    modal = page.locator("#app-modal")
    main = page.locator("#main-content")
    table = page.locator("#learners-table")

    page.locator("#learners-table thead").get_by_label(
        "Select all on this page"
    ).check()
    page.get_by_role("button", name=f"Select all {matching} matching").click()
    main.get_by_role("button", name="Add to cohort", exact=True).click()
    modal.get_by_label("Cohort").select_option(label="Evening group")
    expect(
        modal.get_by_text(f"Add {matching} learners to Evening group.")
    ).to_be_visible()
    modal.get_by_role("button", name="Add to cohort", exact=True).click()

    expect(modal.get_by_text(f"{matching} learners changed.")).to_be_visible()
    assert CohortMembership.objects.filter(cohort=cohort).count() == matching

    # The table refreshes behind the summary; selecting again must wait for it.
    expect(table.locator("tbody td", has_text="Evening group").first).to_be_visible()
    modal.get_by_text("Close", exact=True).click()
    expect(modal).to_be_hidden()
    # The refresh leaves the header checkbox ticked but the selection empty,
    # so it is toggled to select everything again.
    header_checkbox = page.locator("#learners-table thead").get_by_label(
        "Select all on this page"
    )
    header_checkbox.uncheck()
    header_checkbox.check()
    page.get_by_role("button", name=f"Select all {matching} matching").click()
    main.get_by_role("button", name="Remove from cohort", exact=True).click()
    modal.get_by_label("Cohort").select_option(label="Evening group")
    expect(
        modal.get_by_text(f"Remove {matching} learners from Evening group.")
    ).to_be_visible()
    modal.get_by_role("button", name="Remove from cohort", exact=True).click()

    expect(modal.get_by_text(f"{matching} learners changed.")).to_be_visible()
    assert not CohortMembership.objects.filter(cohort=cohort).exists()

    expect(table.locator("tbody td", has_text="Evening group")).to_have_count(0)
    modal.get_by_text("Close", exact=True).click()
    header_checkbox.uncheck()
    header_checkbox.check()
    main.get_by_role("button", name="More actions").click()
    expect(main.get_by_role("menuitem", name="Deactivate")).to_be_visible()
    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(page)


def test_a_background_bulk_run_keeps_the_reader_on_the_table_until_it_finishes(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
    settings,
) -> None:
    settings.BULK_BACKGROUND_THRESHOLD = 1
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    learners = [LearnerFactory(organisation=organisation) for _ in range(2)]
    # Tasks run inline under test, so the run is over before the first poll.
    # Holding the poll at 204 is what shows the in-progress state.
    finished = False

    def status(route: Route) -> None:
        if finished:
            route.continue_()
        else:
            route.fulfill(status=204)

    page.route("**/bulk-runs/*/status/", status)
    # The CSP build of Alpine reports an unsupported directive expression
    # only as a page error.
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    learners_url = interface_url(live_server, organisation.slug, "learners")
    page.goto(learners_url)
    modal = page.locator("#app-modal")
    main = page.locator("#main-content")
    table = page.locator("#learners-table")

    table.locator("thead").get_by_label("Select all on this page").check()
    main.get_by_role("button", name="More actions").click()
    main.get_by_role("menuitem", name="Deactivate").click()
    expect(
        modal.get_by_text("You'll get a notification when it finishes.")
    ).to_be_visible()
    modal.get_by_role("button", name="Deactivate", exact=True).click()

    expect(modal).to_be_hidden()
    expect(page).to_have_url(learners_url)
    expect(main.get_by_text("Deactivate is running…")).to_be_visible()
    expect(main.get_by_role("button", name="More actions")).to_be_disabled()
    expect(
        main.get_by_role("button", name="Add to cohort", exact=True)
    ).to_be_disabled()
    expect(
        main.get_by_role("button", name="More actions").locator("svg.animate-spin")
    ).to_be_visible()
    checkboxes = table.locator("input[name='keys'], input[data-select-all]")
    # A header and a mobile "select all", and a table and a card box per row.
    expect(checkboxes).to_have_count(2 + 2 * len(learners))
    for checkbox in checkboxes.all():
        expect(checkbox).to_be_disabled()

    finished = True

    expect(modal.get_by_text("2 learners changed.")).to_be_visible()
    # The default Status filter hides removed learners, so the refreshed
    # table has no rows left to select.
    expect(table.locator("input[name='keys']")).to_have_count(0)
    modal.get_by_text("Close", exact=True).click()
    expect(modal).to_be_hidden()
    expect(main.get_by_text("Deactivate is running…")).to_be_hidden()
    for checkbox in checkboxes.all():
        expect(checkbox).to_be_enabled()
    assert not Learner.objects.filter(
        pk__in=[learner.pk for learner in learners], is_active=True
    ).exists()
    assert page_errors == []
    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(page)


def test_bulk_deactivate_with_javascript_off_shows_the_result_page(
    browser: Browser,
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    organisation = OrganisationFactory(name="Org A")
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    learners = [LearnerFactory(organisation=organisation) for _ in range(2)]
    # The session cookie carries the login into a context with scripting off.
    context = browser.new_context(java_script_enabled=False)
    context.add_cookies(educator_logged_in_page.context.cookies())
    page = context.new_page()

    try:
        page.goto(interface_url(live_server, organisation.slug, "learners"))
        rows = page.locator("#learners-table tbody input[name='keys']")
        rows.nth(0).check()
        rows.nth(1).check()
        page.get_by_role("button", name="Deactivate", exact=True).first.click()
        page.get_by_role("button", name="Deactivate", exact=True).last.click()

        expect(page.get_by_text("2 learners changed.")).to_be_visible()
        page.get_by_role("link", name="Back to learners").click()
        expect(page).to_have_url(
            interface_url(live_server, organisation.slug, "learners")
        )
    finally:
        context.close()

    assert not any(
        learner.is_active
        for learner in Learner.objects.filter(
            pk__in=[learner.pk for learner in learners]
        )
    )


def test_bulk_add_to_cohort_with_javascript_off_asks_for_the_cohort_first(
    browser: Browser,
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    organisation = OrganisationFactory(name="Org A")
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    cohort = CohortFactory(organisation=organisation, name="Evening group")
    learner = LearnerFactory(organisation=organisation)
    context = browser.new_context(java_script_enabled=False)
    context.add_cookies(educator_logged_in_page.context.cookies())
    page = context.new_page()

    try:
        page.goto(interface_url(live_server, organisation.slug, "learners"))
        page.locator("#learners-table tbody input[name='keys']").first.check()
        page.get_by_role("button", name="Add to cohort", exact=True).first.click()
        page.get_by_label("Cohort", exact=True).select_option(label="Evening group")
        page.get_by_role("button", name="Show what changes").click()
        page.get_by_role("button", name="Add to cohort", exact=True).last.click()

        expect(page.get_by_text("1 learner changed.")).to_be_visible()
    finally:
        context.close()

    assert CohortMembership.objects.filter(cohort=cohort, learner=learner).exists()


def test_mobile_selection_bar_does_not_cover_the_last_card_checkbox(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    """Below md the fixed selection bar sat over the last cards, so their
    checkboxes could not be tapped once a row was ticked."""
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    for _ in range(3):
        LearnerFactory(organisation=organisation)
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(interface_url(live_server, organisation.slug, "learners"))
    checkboxes = page.locator("ul input[name='keys']")

    checkboxes.first.check()
    checkboxes.last.scroll_into_view_if_needed()
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

    topmost_is_checkbox = checkboxes.last.evaluate(
        """el => {
            const box = el.getBoundingClientRect();
            const hit = document.elementFromPoint(
                box.x + box.width / 2, box.y + box.height / 2);
            return hit === el;
        }"""
    )
    assert topmost_is_checkbox
