"""Browser flow for the educator interface on a phone and across the sidebar
breakpoint.

Below ``lg`` the sidebar is a modal ``<dialog>`` opened with ``showModal()``;
from ``lg`` up it docks as a column. The Django test client never runs the
sheet controller, and ``<dialog>`` modality, focus and session history are
browser state.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser, Page, expect

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role
from freedom_ls.tests.playwright_fixtures import sign_in
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

from .helpers import interface_url

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_PHONE = QA_VIEWPORTS[0]
# Wide enough that the sidebar docks as a desktop column.
_DESKTOP = {"width": 1442, "height": 900}


def test_educator_navigates_and_creates_a_cohort_on_a_phone(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    """The navigation sheet and the create-cohort bottom sheet on a phone, and
    the sidebar across the breakpoint:
    - the sheet opens its own dialog, closes on Esc with focus returned, and
      drops its slide under reduced motion;
    - a section link loads over htmx, and switching organisation closes the
      sheet and Back restores the previous organisation;
    - widening past the breakpoint docks the sidebar, however its dialog is
      re-shown, and during its closing transition;
    - the create-cohort sheet fits its field and buttons, keeps its form, and
      asks before discarding a draft;
    - the first Tab on a desktop page reaches the site header;
    - the organisation switcher popover opens under its trigger.
    """
    page = educator_logged_in_page
    organisation_a = OrganisationFactory(name="Org A")
    organisation_b = OrganisationFactory(name="Org B")
    CohortFactory(organisation=organisation_a, name="Alpha Cohort")
    CohortFactory(organisation=organisation_b, name="Beta Cohort")
    assign_object_role(educator_user, organisation_a, "organisation_admin")
    assign_object_role(educator_user, organisation_b, "organisation_admin")
    LearnerFactory(user=UserFactory(), organisation=organisation_a)
    learners_url = interface_url(live_server, organisation_a.slug, "learners")
    cohorts_url = interface_url(live_server, organisation_a.slug, "cohorts")
    page.set_viewport_size(_PHONE)
    sheet = page.locator("dialog[aria-label='Navigation']")
    filter_sheet = page.locator("dialog[aria-label='Filter']")
    toggle = page.get_by_role("button", name="Open navigation panel")
    alpha_link = page.get_by_role("link", name="Alpha Cohort", exact=True)

    # The sidebar and the table's filter sheet are two nested sidePanel
    # components; the nav button must open its own dialog, not the nearer one.
    page.goto(learners_url)
    expect(sheet).to_be_hidden()
    expect(filter_sheet).to_be_hidden()
    toggle.click()
    expect(sheet).to_be_visible()
    expect(filter_sheet).to_be_hidden()
    expect(sheet.locator("#sidebar-nav")).to_be_visible()

    body = sheet.locator(".side-panel-body")
    expect(body).to_have_css("border-top-left-radius", "16px")
    expect(body).to_have_css("border-top-right-radius", "16px")

    # The sheet has no close control; Esc closes it and returns focus to the
    # toggle that opened it.
    expect(sheet.get_by_role("button", name="Close navigation")).to_have_count(0)
    page.keyboard.press("Escape")
    expect(sheet).to_be_hidden()
    expect(toggle).to_be_focused()

    # The slide is a CSS transition that reduced motion switches off.
    page.emulate_media(reduced_motion="reduce")
    toggle.click()
    expect(sheet).to_be_visible()
    expect(sheet).to_have_css("transition-duration", "0s")

    # A section link loads over htmx (a surviving window marker proves no
    # document load), dismisses the sheet and moves focus into the content:
    # the toggle was swapped out with the content it sat in.
    page.evaluate("window.__noReloadMarker = true")
    sheet.get_by_role("link", name="Cohorts").click()
    expect(page).to_have_url(cohorts_url)
    expect(alpha_link).to_be_visible()
    expect(sheet).to_be_hidden()
    expect(page.locator("#main-content")).to_be_focused()
    assert page.evaluate("window.__noReloadMarker === true")
    page.go_back()
    expect(page).to_have_url(learners_url)

    # Switching organisation from the sheet closes it, and Back restores the
    # organisation switched away from with its content, not a mismatch.
    page.goto(cohorts_url)
    toggle.click()
    expect(sheet).to_be_visible()
    page.get_by_role("button", name="Switch organisation").click()
    page.get_by_role("menuitemradio", name="Org B").click()
    expect(page).to_have_url(interface_url(live_server, organisation_b.slug, "cohorts"))
    expect(sheet).to_be_hidden()
    expect(page.get_by_role("link", name="Beta Cohort", exact=True)).to_be_visible()
    page.go_back()
    expect(page).to_have_url(cohorts_url)
    expect(sheet).to_be_hidden()
    expect(page.locator("#organisation-switcher")).to_contain_text("Org A")
    expect(alpha_link).to_be_visible()

    # Widening past the sidebar breakpoint with the sheet open docks it.
    toggle.click()
    expect(sheet).to_be_visible()
    expect(page.locator("dialog[aria-label='Navigation']:modal")).to_have_count(1)
    page.set_viewport_size(_DESKTOP)
    # Docking closes the modal and re-shows the dialog without modality, so
    # the sheet is briefly hidden in between: settle on non-modal first.
    expect(page.locator("dialog[aria-label='Navigation']:modal")).to_have_count(0)
    expect(sheet).to_be_visible()
    # The docked column and the content settle over a few frames, so the
    # geometry is waited for rather than read once: a sidebar at least 200px
    # wide with the content, at least 800px wide, laid out to its right.
    page.wait_for_function(
        """() => {
            const sidebar = document.querySelector("dialog[aria-label='Navigation']");
            const main = document.getElementById("main-content");
            if (!sidebar || !main) return false;
            const s = sidebar.getBoundingClientRect();
            const m = main.getBoundingClientRect();
            return s.width >= 200 && m.width >= 800 && m.x >= s.x + s.width;
        }"""
    )

    # The create-cohort bottom sheet shows its field and both buttons without
    # scrolling, and Cancel dismisses it.
    page.set_viewport_size(_PHONE)
    page.goto(cohorts_url)
    expect(sheet).to_be_hidden()
    dialog = page.locator("#app-modal")
    create_trigger = page.get_by_role("button", name="Create cohort")
    create_trigger.click()
    expect(dialog).to_be_visible()
    name_field = dialog.get_by_label("Name")
    cancel = dialog.get_by_role("button", name="Cancel")
    expect(name_field).to_be_in_viewport()
    expect(cancel).to_be_in_viewport()
    expect(dialog.get_by_role("button", name="Add", exact=True)).to_be_in_viewport()

    # The sheet slides out over its closing transition, so its form stays
    # until the next open replaces it rather than sending an empty sheet down
    # the screen.
    name_field.fill("Half-typed cohort")
    cancel.click()
    expect(page.locator("#app-modal-body form")).to_have_count(1)
    expect(dialog).to_be_hidden()
    create_trigger.click()
    expect(dialog).to_be_visible()
    expect(name_field).to_have_value("")

    # Escape still reaches the dialog once widening docks the sidebar behind it.
    page.set_viewport_size(_DESKTOP)
    expect(dialog).to_be_visible()
    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()
    expect(sheet).to_be_visible()

    # A dirty dialog asks before discarding.
    page.set_viewport_size(_PHONE)
    page.goto(cohorts_url)
    expect(sheet).to_be_hidden()
    create_trigger.click()
    expect(dialog).to_be_visible()
    name_field.fill("Half-typed cohort")
    page.set_viewport_size(_DESKTOP)
    expect(dialog).to_be_visible()
    name_field.focus()
    page.keyboard.press("Escape")
    discard = page.get_by_role("dialog", name="Discard changes?")
    expect(discard).to_be_visible()
    discard.get_by_role("button", name="Discard").click()
    expect(dialog).to_be_hidden()

    # On a fresh desktop page the first Tab reaches the site header.
    page.goto(cohorts_url)
    expect(sheet).to_be_visible()
    assert page.evaluate("document.activeElement === document.body")
    page.keyboard.press("Tab")
    assert page.evaluate(
        "document.querySelector('header.header').contains(document.activeElement)"
    )

    # The closing-transition check below needs the slide animation back on.
    page.emulate_media(reduced_motion="no-preference")
    page.set_viewport_size(QA_VIEWPORTS[2])
    page.goto(cohorts_url)
    expect(sheet).to_be_visible()
    docked_beside_content = """() => {
        const sidebar = document.querySelector("dialog[aria-label='Navigation']");
        const main = document.getElementById("interface-main");
        const s = sidebar.getBoundingClientRect();
        const m = main.getBoundingClientRect();
        return s.width > 0 && s.width < window.innerWidth / 2 && m.x >= s.x + s.width - 1;
    }"""
    page.wait_for_function(docked_beside_content)

    # The grid's columns follow the dialog's own open state, so a sidebar
    # re-shown directly, without the controller, is still a column.
    page.evaluate("document.querySelector(\"dialog[aria-label='Navigation']\").close()")
    page.wait_for_function(
        "() => document.getElementById('interface-main').getBoundingClientRect().x === 0"
    )
    page.evaluate("document.querySelector(\"dialog[aria-label='Navigation']\").show()")
    page.wait_for_function(docked_beside_content)

    # Widening past the breakpoint while the sheet is open, with its closing
    # transition running, still docks it: the sheet stays in the top layer
    # until the transition ends, and a dock attempted before then is refused by
    # the browser.
    page.set_viewport_size(_PHONE)
    expect(sheet).to_be_hidden()
    toggle.click()
    expect(page.locator("dialog[aria-label='Navigation']:modal")).to_have_count(1)
    page.set_viewport_size(QA_VIEWPORTS[2])
    expect(page.locator("dialog[aria-label='Navigation']:modal")).to_have_count(0)
    expect(sheet).to_be_visible()
    page.wait_for_function(docked_beside_content)

    # Organisation switcher popover.
    page.set_viewport_size({"width": 1024, "height": 768})
    page.goto(cohorts_url)
    trigger = page.get_by_role("button", name="Switch organisation")
    trigger.click()
    expect(page.get_by_role("menuitemradio").first).to_be_visible()
    trigger_box = trigger.bounding_box()
    options_box = page.get_by_role("menu", name="Switch organisation").bounding_box()
    assert trigger_box is not None
    assert options_box is not None
    assert abs(options_box["y"] - (trigger_box["y"] + trigger_box["height"])) < 16, (
        "switcher popover not directly under its trigger at 1024px"
    )
    assert options_box["x"] >= trigger_box["x"] - 1, (
        "switcher popover starts left of its trigger at 1024px"
    )
    assert options_box["x"] < trigger_box["x"] + trigger_box["width"], (
        "switcher popover starts right of its trigger at 1024px"
    )


def test_a_page_with_a_sortable_table_keeps_its_sidebar_across_the_breakpoint(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    """A table with sort options and no filters renders no filter sheet. Its
    toolbar must not run a side panel of its own: one that did adopted the
    navigation dialog, closed it when the viewport widened past the sidebar
    breakpoint and, being mobile-only, never docked it again."""
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    assign_object_role(educator_user, organisation, "organisation_admin")
    course = CourseFactory(title="Algebra")
    CohortCourseRegistrationFactory(
        cohort=CohortFactory(organisation=organisation), course=course
    )
    course_url = interface_url(live_server, organisation.slug, f"courses/{course.pk}")
    sidebar = page.locator("dialog[aria-label='Navigation']")

    page.set_viewport_size(QA_VIEWPORTS[0])
    page.goto(course_url)
    expect(page.get_by_role("button", name="Sort")).to_be_visible()
    expect(sidebar).to_be_hidden()
    page.get_by_role("button", name="Open navigation panel").click()
    expect(page.locator("dialog[aria-label='Navigation']:modal")).to_have_count(1)
    # Let the sheet's opening transition finish, as a reader's would have.
    page.wait_for_timeout(400)
    page.set_viewport_size(QA_VIEWPORTS[2])
    expect(page.locator("dialog[aria-label='Navigation']:modal")).to_have_count(0)
    expect(sidebar).to_be_visible()
    page.wait_for_function(
        """() => {
            const sidebar = document.querySelector("dialog[aria-label='Navigation']");
            const main = document.getElementById("interface-main");
            const s = sidebar.getBoundingClientRect();
            const m = main.getBoundingClientRect();
            return s.width > 0 && s.width < window.innerWidth / 2 && m.x >= s.x + s.width - 1;
        }"""
    )


def test_dashboard_fills_its_lazy_figures_without_overflow_at_every_width(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Dashboard Org")
    cohort = CohortFactory(organisation=organisation, name="Flagged Cohort")
    # A member is only flagged when the cohort gives them something to do.
    course = CourseFactory()
    course.items.create(child=TopicFactory(), order=0)
    CohortCourseRegistrationFactory(cohort=cohort, course=course)
    CohortMembershipFactory(
        cohort=cohort,
        learner__user=UserFactory(first_name="Thandi", last_name="Mokoena"),
    )
    assign_object_role(educator_user, organisation, "organisation_admin")
    dashboard_url = interface_url(live_server, organisation.slug, "dashboard")

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(dashboard_url)
        attention_tile = page.locator("dl", has_text="Learners needing attention")
        expect(attention_tile.locator("dd").first).to_have_text("1")
        expect(
            page.get_by_role("link", name="Quick view: Thandi Mokoena", exact=True)
        ).to_be_visible()
        expect(page.get_by_role("link", name="Flagged Cohort").first).to_be_visible()
        assert_no_horizontal_overflow(page)


def test_navigation_without_javascript_flow(
    browser: Browser,
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    """With scripting off nothing opens the navigation dialog, so it is laid
    out statically:
    - at 1920 it docks as the left column, in the same place and width as with
      scripting on;
    - on a phone it is a block above the content.
    """
    organisation = OrganisationFactory(name="Org A")
    assign_object_role(educator_user, organisation, "organisation_admin")
    assign_object_role(
        educator_user, OrganisationFactory(name="Org B"), "organisation_admin"
    )
    url = interface_url(live_server, organisation.slug, "learners")
    page = educator_logged_in_page
    page.set_viewport_size(QA_VIEWPORTS[2])
    page.goto(url)
    with_script = page.locator("dialog[aria-label='Navigation']").bounding_box()

    context = browser.new_context(java_script_enabled=False)
    try:
        plain = context.new_page()
        sign_in(plain, live_server, educator_user)
        nav = plain.locator("dialog[aria-label='Navigation']")
        open_navigation = plain.get_by_role("button", name="Open navigation panel")

        # Left column at 1920.
        plain.set_viewport_size(QA_VIEWPORTS[2])
        plain.goto(url)
        expect(nav.get_by_role("link", name="Cohorts")).to_be_visible()
        expect(nav.get_by_role("link", name="Learners")).to_be_visible()
        expect(nav.get_by_title("Org A")).to_be_visible()
        expect(open_navigation).to_be_hidden()
        without_script = nav.bounding_box()
        content = plain.locator("#interface-main").bounding_box()
        assert without_script is not None
        assert content is not None
        assert with_script is not None
        assert without_script["x"] == with_script["x"], (
            "scriptless navigation not in the scripted column's place at 1920px"
        )
        assert without_script["width"] == with_script["width"], (
            "scriptless navigation not the scripted column's width at 1920px"
        )
        assert content["x"] >= without_script["x"] + without_script["width"], (
            "content overlaps the scriptless navigation column at 1920px"
        )
        assert_no_horizontal_overflow(plain)

        # Block above the content on a phone.
        plain.set_viewport_size(_PHONE)
        plain.goto(url)
        expect(nav.get_by_role("link", name="Cohorts")).to_be_visible()
        expect(nav.get_by_title("Org A")).to_be_visible()
        expect(open_navigation).to_be_hidden()
        box = nav.bounding_box()
        content = plain.locator("#interface-main").bounding_box()
        assert box is not None
        assert content is not None
        assert box["y"] + box["height"] <= content["y"] + 1, (
            "scriptless navigation not above the content at 375px"
        )
        assert_no_horizontal_overflow(plain)
    finally:
        context.close()
