"""E2E Playwright tests for where the docked quick view sits on a real page.

From 1280px up the drawer is docked beside the page rather than laid over it:
it starts below the site header, and the page content makes room for it, so
the list's actions and every table column stay reachable while it is open.
The stub-harness layout tests in panel_framework cover the push, but that
harness renders no site header, so only a real page shows the drawer clearing
it.
"""

from __future__ import annotations

import pytest
from guardian.shortcuts import assign_perm
from playwright.sync_api import FloatRect, Locator, Page, expect

from freedom_ls.accounts.models import User
from freedom_ls.learner_management.factories import CohortFactory, LearnerFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role

from .helpers import interface_url

pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def _box(locator: Locator) -> FloatRect:
    box = locator.bounding_box()
    assert box is not None
    return box


@pytest.mark.parametrize(
    "viewport",
    [{"width": 1920, "height": 1080}, {"width": 1280, "height": 800}],
    ids=["1920", "1280"],
)
def test_the_docked_drawer_leaves_the_header_actions_and_table_uncovered(
    live_server,
    educator_logged_in_page: Page,
    educator_user: User,
    viewport: dict[str, int],
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    CohortFactory(organisation=organisation, name="Year 9 Maths")
    assign_object_role(educator_user, organisation, "organisation_admin")
    assign_perm("freedom_ls_learner_management.add_cohort", educator_user)
    page.set_viewport_size(viewport)

    page.goto(interface_url(live_server, organisation.slug, "cohorts"))
    page.get_by_role("link", name="Quick view: Year 9 Maths").click()

    drawer = page.locator("#quick-view")
    expect(drawer).to_be_visible()
    expect(page.locator("dialog:modal")).to_have_count(0)
    # The slide-in transform transitions over 200ms, so wait for it to settle
    # before measuring the box, or the read races the animation.
    expect(drawer).to_have_css("transform", "none")

    drawer_box = _box(drawer)
    header_box = _box(page.locator("header.header"))
    create_box = _box(page.get_by_role("button", name="Create Cohort"))
    table_box = _box(page.locator("#main-content table"))
    assert drawer_box["y"] >= header_box["y"] + header_box["height"] - 1
    assert create_box["x"] + create_box["width"] <= drawer_box["x"]
    assert table_box["x"] + table_box["width"] <= drawer_box["x"]

    page.get_by_role("button", name="Create Cohort").click()

    expect(page.locator("#app-modal")).to_be_visible()


def test_pagination_stays_inside_the_card_beside_a_docked_drawer(
    live_server,
    educator_logged_in_page: Page,
    educator_user: User,
) -> None:
    """The learners table's data-table card narrows once the quick-view
    drawer docks at xl. Enough learners to need the full numbered-pages
    variant (pages, ellipsis, Next) must still wrap inside the card rather
    than run on under the drawer."""
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    assign_object_role(educator_user, organisation, "organisation_admin")
    LearnerFactory.create_batch(
        51, organisation=organisation, user__first_name="Learner"
    )
    page.set_viewport_size({"width": 1400, "height": 900})

    page.goto(interface_url(live_server, organisation.slug, "learners"))
    page.get_by_role("link", name="Quick view: Learner", exact=True).first.click()

    drawer = page.locator("#quick-view")
    expect(drawer).to_be_visible()
    expect(drawer).to_have_css("transform", "none")

    next_link = page.get_by_role("link", name="Next", exact=True)
    expect(next_link).to_be_visible()
    drawer_box = _box(drawer)
    next_box = _box(next_link)
    assert next_box["x"] + next_box["width"] <= drawer_box["x"]


def test_docked_drawer_clears_the_header_after_widening_from_mobile(
    live_server,
    educator_logged_in_page: Page,
    educator_user: User,
) -> None:
    """The docked drawer's top offset is read from a CSS var captured once,
    on load, from the site header's rendered height. Opening the page at a
    mobile viewport (a shorter header) and then widening to desktop — with
    no reload in between — must not leave the drawer pinned to that stale,
    shorter height once it docks."""
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    assign_object_role(educator_user, organisation, "organisation_admin")
    LearnerFactory(organisation=organisation, user__first_name="Learner")
    page.set_viewport_size({"width": 375, "height": 812})

    page.goto(interface_url(live_server, organisation.slug, "learners"))
    page.set_viewport_size({"width": 1400, "height": 900})
    page.get_by_role("link", name="Quick view: Learner", exact=True).first.click()

    drawer = page.locator("#quick-view")
    expect(drawer).to_be_visible()
    expect(drawer).to_have_css("transform", "none")

    drawer_box = _box(drawer)
    header_box = _box(page.locator("header.header"))
    assert drawer_box["y"] >= header_box["y"] + header_box["height"] - 1


@pytest.mark.parametrize("width", [1920, 1442, 1280])
def test_the_page_stays_put_when_the_docked_drawer_opens_and_closes(
    live_server,
    educator_logged_in_page: Page,
    educator_user: User,
    width: int,
) -> None:
    """The content column is anchored to the sidebar, so only its right
    edge gives way to the docked drawer: the title and the table's left edge
    do not move when the drawer opens, nor when it closes."""
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    CohortFactory(organisation=organisation, name="Year 9 Maths")
    assign_object_role(educator_user, organisation, "organisation_admin")
    page.set_viewport_size({"width": width, "height": 900})

    page.goto(interface_url(live_server, organisation.slug, "cohorts"))
    title = page.locator("#main-content h1")
    table = page.locator("#main-content table")
    at_rest = (_box(title)["x"], _box(table)["x"])

    page.get_by_role("link", name="Quick view: Year 9 Maths").click()
    drawer = page.locator("#quick-view")
    expect(drawer).to_be_visible()
    expect(drawer).to_have_css("transform", "none")

    assert (_box(title)["x"], _box(table)["x"]) == at_rest

    drawer.get_by_role("button", name="Close").click()
    expect(drawer).to_be_hidden()

    assert (_box(title)["x"], _box(table)["x"]) == at_rest
