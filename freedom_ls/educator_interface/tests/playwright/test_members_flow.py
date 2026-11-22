"""E2E Playwright flow for the Staff list: add a user as a cohort admin on
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

from .helpers import TOUCH_HEIGHT, interface_url

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
    LearnerFactory(
        organisation=organisation,
        user__email="existing@example.com",
        user__first_name="Erin",
        user__last_name="Existing",
    )
    UserFactory(email="second@example.com", first_name="Sam", last_name="Second")
    failed: list[str] = []

    def record_failure(response: Response) -> None:
        if response.status >= 400:
            failed.append(f"{response.status} {response.url}")

    page.goto(interface_url(live_server, organisation.slug, "staff"))
    page.on("response", record_failure)
    modal = page.locator("#app-modal")
    main = page.locator("#main-content")

    main.get_by_role("button", name="Add staff member", exact=True).first.click()
    combobox = modal.get_by_role("combobox", name="Email address")
    combobox.press_sequentially("eri")
    expect(modal.get_by_role("option")).to_have_count(1)
    expect(modal.get_by_role("option")).to_contain_text("Erin Existing")
    combobox.press("ArrowDown")
    expect(combobox).to_have_attribute("aria-expanded", "true")
    combobox.press("Escape")
    expect(combobox).to_have_attribute("aria-expanded", "false")
    expect(modal).to_be_visible()
    combobox.press("ArrowDown")
    combobox.press("Enter")
    expect(modal.get_by_text("Existing account: Erin Existing")).to_be_visible()

    modal.get_by_text("Cohort admin", exact=True).click()
    modal.get_by_label("Alpha Cohort").check()
    modal.get_by_label("Beta Cohort").check()
    expect(modal.get_by_text("2 selected")).to_be_visible()
    modal.get_by_role("button", name="Next", exact=True).click()

    expect(modal.get_by_text("Scope: Alpha Cohort and Beta Cohort")).to_be_visible()
    modal.get_by_role("button", name="Confirm", exact=True).click()

    expect(modal).to_be_hidden()
    row = main.get_by_role("row").filter(has_text="Erin Existing")
    expect(row.get_by_text("Cohort admin")).to_be_visible()
    expect(row.get_by_text("Alpha Cohort")).to_be_visible()
    expect(row.get_by_text("Beta Cohort")).to_be_visible()

    row.get_by_role(
        "button", name="Change Cohort admin cohorts for Erin Existing", exact=True
    ).click()
    modal.get_by_label("Beta Cohort").uncheck()
    modal.get_by_role("button", name="Change cohorts", exact=True).click()
    expect(modal.get_by_text("Deactivates on: Beta Cohort")).to_be_visible()
    modal.get_by_role("button", name="Change cohorts", exact=True).click()

    expect(modal).to_be_hidden()
    expect(row.get_by_text("Alpha Cohort")).to_be_visible()
    expect(row.get_by_text("Beta Cohort")).to_have_count(0)

    row.get_by_role(
        "button", name="Deactivate Cohort admin for Erin Existing", exact=True
    ).click()
    expect(modal.get_by_text("They lose")).to_be_visible()
    modal.get_by_role("button", name="Deactivate", exact=True).click()

    expect(modal).to_be_hidden()
    expect(row.get_by_text("No roles yet")).to_be_visible()
    expect(row.get_by_text("Cohort admin")).to_have_count(0)

    main.get_by_role("button", name="Add staff member", exact=True).first.click()
    modal.get_by_role("combobox", name="Email address").fill("second@example.com")
    modal.get_by_role("button", name="Next", exact=True).click()
    modal.get_by_text("No roles yet", exact=True).click()
    modal.get_by_role("button", name="Next", exact=True).click()
    modal.get_by_role("button", name="Confirm", exact=True).click()
    expect(modal).to_be_hidden()
    second_row = main.get_by_role("row").filter(has_text="Sam Second")
    expect(second_row.get_by_text("No roles yet")).to_be_visible()

    second_row.get_by_role("button", name="Add role").locator(
        "visible=true"
    ).first.click()
    modal.get_by_text("Cohort viewer", exact=True).click()
    modal.get_by_label("Alpha Cohort").check()
    modal.get_by_role("button", name="Next", exact=True).click()
    modal.get_by_role("button", name="Confirm", exact=True).click()
    expect(modal).to_be_hidden()
    expect(second_row.get_by_text("Cohort viewer")).to_be_visible()
    page.wait_for_load_state("networkidle")
    assert failed == []

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(page)

    page.set_viewport_size(QA_VIEWPORTS[0])
    page.goto(interface_url(live_server, organisation.slug, "staff"))
    expect(main.locator("[data-card-primary-line]").first).to_be_visible()


def _staff_buttons_outside_the_viewport(page: Page) -> list[str]:
    """The labels of the Staff list's visible buttons that are cut off by, or
    sit beyond, either side of the viewport."""
    labels: list[str] = page.evaluate(
        """() => [...document.querySelectorAll('[data-table-region] .btn')]
            .filter((button) => button.offsetParent !== null)
            .filter((button) => {
                const box = button.getBoundingClientRect();
                return box.left < 0 || box.right > window.innerWidth;
            })
            .map((button) => button.textContent.trim())"""
    )
    return labels


def test_staff_list_layout_flow(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    """The Staff list's layout across widths and its filter reset:
    - a table at 1280, cards beside the quick view and cards at 768, with no
      button cut off by the viewport edge;
    - row actions and the toolbar's Filter and Sort meet the 44px touch target
      at 375;
    - a nameless member's long email does not scroll a phone sideways;
    - the change-cohorts dialog titled with a long email stays inside a 375px
      viewport;
    - Clear filters after a no-match search empties the search box.
    """
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    cohort = CohortFactory(organisation=organisation, name="Alpha Cohort")
    long_name_cohort = CohortFactory(
        organisation=organisation, name="A Cohort With A Rather Long Name Indeed"
    )
    colleague = UserFactory(first_name="Cara", last_name="Colleague")
    assign_role(grantor, colleague, "cohort_viewer", cohort)
    viewer = UserFactory(
        email="viewer@example.com", first_name="Vee", last_name="Viewer"
    )
    assign_role(grantor, viewer, "cohort_viewer", cohort)
    nameless_admin = UserFactory(
        email="nameless.lower.educator.with.a.very.long.address@example.com",
        first_name="",
        last_name="",
    )
    assign_role(grantor, nameless_admin, "organisation_admin", organisation)
    nameless_viewer = UserFactory(
        email="nameless.cohort.viewer.with.a.very.long.address@example.com",
        first_name="",
        last_name="",
    )
    assign_role(grantor, nameless_viewer, "cohort_viewer", long_name_cohort)
    staff_url = interface_url(live_server, organisation.slug, "staff")
    main = page.locator("#main-content")
    table = main.get_by_role("table")
    card = main.locator("[data-card-primary-line]").first

    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(staff_url)
    expect(table, "table hidden at 1280px").to_be_visible()
    expect(card, "cards shown at 1280px without the quick view").to_be_hidden()
    main.get_by_role("row").filter(has_text="Cara Colleague").locator(
        "[hx-get*='__quick-view']"
    ).click()
    expect(page.get_by_text("Quick view", exact=True)).to_be_visible()
    expect(card, "cards hidden beside the quick view").to_be_visible()
    expect(table, "table shown beside the quick view").to_be_hidden()
    assert _staff_buttons_outside_the_viewport(page) == [], (
        "button cut off beside the quick view at 1280px"
    )
    assert_no_horizontal_overflow(page)

    page.set_viewport_size({"width": 768, "height": 1024})
    page.goto(staff_url)
    expect(card, "cards hidden at 768px").to_be_visible()
    expect(table, "table shown at 768px").to_be_hidden()
    assert _staff_buttons_outside_the_viewport(page) == [], "button cut off at 768px"
    assert_no_horizontal_overflow(page)

    page.set_viewport_size(QA_VIEWPORTS[0])
    page.goto(staff_url)
    vee_card = main.locator("li").filter(has_text="Vee Viewer")
    expect(vee_card).to_be_visible()
    for control in (
        vee_card.get_by_role(
            "button", name="Deactivate Cohort viewer for Vee Viewer", exact=True
        ),
        vee_card.get_by_role("button", name="Deactivate Vee Viewer", exact=True),
        main.get_by_role("button", name="Filter"),
        main.get_by_role("button", name="Sort"),
    ):
        height = control.evaluate(TOUCH_HEIGHT)
        assert round(height) >= 44, f"{control} is {height}px high to the touch"

    # A nameless member is shown by their email, which used to run past the
    # card edge.
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(staff_url)
    expect(
        main.get_by_text(nameless_admin.email).locator("visible=true").first,
        "long nameless email not visible at 390px",
    ).to_be_visible()
    assert_no_horizontal_overflow(page)

    # The dialog title wraps and the host clips, so nothing pushes the dialog
    # off the left edge or scrolls the page sideways.
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(staff_url)
    main.get_by_role(
        "button",
        name=f"Change Cohort viewer cohorts for {nameless_viewer.email}",
        exact=True,
    ).first.click()
    modal = page.locator("#app-modal")
    expect(
        modal.get_by_role("heading", name=f"Change cohorts for {nameless_viewer.email}")
    ).to_be_visible()
    assert_no_horizontal_overflow(page)
    box = modal.bounding_box()
    assert box is not None
    assert box["x"] >= 0, "change-cohorts dialog off the left edge at 375px"
    assert box["x"] + box["width"] <= 375, (
        "change-cohorts dialog past the right edge at 375px"
    )
    assert modal.evaluate("el => el.scrollWidth <= el.clientWidth"), (
        "change-cohorts dialog scrolls sideways at 375px"
    )

    # The search box survives the region swap, so the server's empty value has
    # to reach it; otherwise the box contradicts the restored list.
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(staff_url)
    search = main.locator("#staff-q")
    search.fill("zzz")
    # The empty state renders once for the table and once for the card list.
    expect(
        main.get_by_text("No staff members match these filters.").first
    ).to_be_visible()
    main.get_by_role("link", name="Clear filters", exact=True).first.click()
    expect(main.get_by_text("No staff members match these filters.")).to_have_count(0)
    expect(search, "search box not emptied by Clear filters").to_have_value("")


def test_add_staff_dialog_layout_flow(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    """The Add staff dialog's layout:
    - the search results listbox shares the email input's left edge and width
      at 1280 and 375;
    - the Next button stays in view on the role step at 375 with 30 cohorts.
    """
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    for number in range(30):
        CohortFactory(organisation=organisation, name=f"Cohort {number:02d}")
    LearnerFactory(
        organisation=organisation,
        user__email="existing@example.com",
        user__first_name="Erin",
        user__last_name="Existing",
    )
    staff_url = interface_url(live_server, organisation.slug, "staff")
    modal = page.locator("#app-modal")
    add_staff = page.locator("#main-content").get_by_role(
        "button", name="Add staff member", exact=True
    )

    # The results listbox used to sit indented from the input it drops down from.
    for width in (1280, 375):
        page.set_viewport_size({"width": width, "height": 800})
        page.goto(staff_url)
        add_staff.first.click()
        modal.get_by_label("Email address").fill("existing")
        listbox = modal.locator("#staff-search-listbox")
        expect(listbox, f"search results hidden at {width}px").to_be_visible()
        input_box = modal.locator("#staff-search-input").bounding_box()
        list_box = listbox.bounding_box()
        assert input_box is not None
        assert list_box is not None
        assert abs(list_box["x"] - input_box["x"]) <= 1, (
            f"results listbox left edge differs from the input at {width}px"
        )
        assert abs(list_box["width"] - input_box["width"]) <= 1, (
            f"results listbox width differs from the input at {width}px"
        )

    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(staff_url)
    add_staff.first.click()
    modal.get_by_label("Email address").fill("existing@example.com")
    # Clicking Next while the as-you-type search is still pending loses the click
    # on a loaded machine, so wait for the search to swap in its results first.
    expect(modal.locator("#staff-search-results")).not_to_have_attribute(
        "data-state", "prompt"
    )
    modal.get_by_role("button", name="Next", exact=True).click()
    modal.get_by_text("Cohort admin", exact=True).click()
    expect(
        modal.get_by_role("button", name="Next", exact=True),
        "Next button out of view on the role step at 375px",
    ).to_be_in_viewport(ratio=1)
