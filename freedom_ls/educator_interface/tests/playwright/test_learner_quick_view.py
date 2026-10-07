"""E2E Playwright tests for the learner drawer opened from the Learners table.

The Django test client coverage of LearnerQuickView's fields lives in
educator_interface/tests/test_quick_views.py. What only a browser shows is
that the quick-view trigger beside a learner's name opens the real
#quick-view drawer, that its Open control leads to the learner's own page,
that the drawer keeps its title on reopen, and that a learnerChanged domain
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
    assign_object_role(educator_user, organisation, "organisation_admin")
    cohort = CohortFactory(organisation=organisation, name="Year 9 Maths")
    learner = LearnerFactory(
        organisation=organisation,
        user=UserFactory(
            first_name="Ada", last_name="Lovelace", email="ada@example.com"
        ),
    )
    CohortMembershipFactory(learner=learner, cohort=cohort)

    page.goto(interface_url(live_server, organisation.slug, "learners"))
    page.get_by_role("link", name="Quick view: Ada", exact=True).click()

    expect(page.locator("#quick-view")).to_be_visible()
    expect(page.locator("#quick-view-subtitle")).to_have_text("ada@example.com")
    expect(page.locator("#quick-view-body")).to_contain_text("Year 9 Maths")

    page.locator("#quick-view-open").click()

    expect(page).to_have_url(
        interface_url(live_server, organisation.slug, f"learners/{learner.pk}")
    )


def test_the_drawer_title_is_the_learners_name_and_stays_so_on_reopen(
    live_server,
    educator_logged_in_page: Page,
    educator_user: User,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    assign_object_role(educator_user, organisation, "organisation_admin")
    LearnerFactory(
        organisation=organisation,
        user=UserFactory(first_name="Ada", last_name="Lovelace"),
    )
    title = page.locator("#quick-view-title")

    page.goto(interface_url(live_server, organisation.slug, "learners"))
    first_name = page.get_by_role("link", name="Quick view: Ada", exact=True)
    first_name.click()
    expect(page.locator("#quick-view-body")).not_to_have_attribute("aria-busy", "true")
    expect(title).to_have_text("Ada Lovelace")

    page.keyboard.press("Escape")
    expect(page.locator("#quick-view")).to_be_hidden()
    first_name.click()
    expect(page.locator("#quick-view")).to_be_visible()
    expect(title).to_have_text("Ada Lovelace")


def test_escape_closes_only_the_topmost_dropdown_leaving_the_drawer_open(
    live_server,
    educator_logged_in_page: Page,
    educator_user: User,
) -> None:
    """A dropdown menu opened over the drawer is its own layer: one Esc
    dismisses the dropdown and leaves the drawer open, a second Esc then
    closes the drawer. A single Esc used to close both."""
    page = educator_logged_in_page
    organisation_a = OrganisationFactory(name="Org A")
    organisation_b = OrganisationFactory(name="Org B")
    assign_object_role(educator_user, organisation_a, "organisation_admin")
    assign_object_role(educator_user, organisation_b, "organisation_admin")
    LearnerFactory(
        organisation=organisation_a,
        user=UserFactory(first_name="Ada", last_name="Lovelace"),
    )

    page.goto(interface_url(live_server, organisation_a.slug, "learners"))
    page.get_by_role("link", name="Quick view: Ada", exact=True).click()
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
    assign_object_role(educator_user, organisation, "organisation_admin")
    learner = LearnerFactory(
        organisation=organisation,
        user=UserFactory(
            first_name="Ada", last_name="Lovelace", email="ada@example.com"
        ),
    )

    page.goto(interface_url(live_server, organisation.slug, "learners"))
    page.get_by_role("link", name="Quick view: Ada", exact=True).click()
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


@pytest.mark.parametrize(
    "viewport",
    [{"width": 1440, "height": 900}, {"width": 390, "height": 844}],
    ids=["table", "cards"],
)
def test_every_rows_quick_view_trigger_lines_up_whatever_the_name_length(
    live_server,
    educator_logged_in_page: Page,
    educator_user: User,
    viewport: dict[str, int],
) -> None:
    page = educator_logged_in_page
    page.set_viewport_size(viewport)
    organisation = OrganisationFactory(name="Org A")
    assign_object_role(educator_user, organisation, "organisation_admin")
    for first_name in ("Al", "Christopher"):
        LearnerFactory(
            organisation=organisation,
            user=UserFactory(first_name=first_name, last_name="Lovelace"),
        )

    page.goto(interface_url(live_server, organisation.slug, "learners"))

    edges = []
    for first_name in ("Al", "Christopher"):
        trigger = page.get_by_role("link", name=f"Quick view: {first_name}", exact=True)
        box = trigger.bounding_box()
        assert box is not None
        edges.append(box["x"] + box["width"])
    assert abs(edges[0] - edges[1]) < 1
