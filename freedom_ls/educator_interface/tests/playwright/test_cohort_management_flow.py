"""Browser flows for managing cohorts and learners as an educator.

The Django test client coverage of the organisation switcher, the cohort
create and delete actions, the denial fragment and the learner quick view
lives in the sibling ``tests/`` modules. What only a browser shows is covered
here: keyboard operation, focus, the native ``#app-modal`` and ``#quick-view``
layers, htmx swaps replacing open dialogs, and layout at real widths.
"""

from __future__ import annotations

import re

import pytest
from guardian.shortcuts import assign_perm
from playwright.sync_api import FloatRect, Locator, Page, Response, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Cohort
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import (
    assign_object_role,
    remove_object_role,
)
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

from .helpers import interface_url

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_LONG_NAME = "Balasubramaniamnathan" * 3
# Widths from 1280px up, where the quick view docks beside the page.
_DOCKED_WIDTHS = (1920, 1442, 1280)


def _box(locator: Locator) -> FloatRect:
    box = locator.bounding_box()
    assert box is not None
    return box


def _quick_view_trigger_edge(page: Page, first_name: str) -> float:
    box = _box(page.get_by_role("link", name=f"Quick view: {first_name}", exact=True))
    return box["x"] + box["width"]


def _assert_quick_view_triggers_line_up(page: Page) -> None:
    """Names of different lengths put every row's trigger at the same edge."""
    assert (
        abs(
            _quick_view_trigger_edge(page, "Al")
            - _quick_view_trigger_edge(page, "Christopher")
        )
        < 1
    )


def _open_drawer(page: Page, trigger: Locator) -> Locator:
    """Open the quick view from its trigger and wait for it to stop sliding in."""
    trigger.click()
    drawer = page.locator("#quick-view")
    expect(drawer).to_be_visible()
    # The slide-in transform transitions over 200ms; measuring before it
    # settles races the animation.
    expect(drawer).to_have_css("transform", "none")
    return drawer


def test_educator_manages_cohorts_and_learners(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation_a = OrganisationFactory(name="Org A")
    organisation_b = OrganisationFactory(name="Org B")
    CohortFactory(organisation=organisation_b, name="Org B Cohort")
    year_nine = CohortFactory(organisation=organisation_a, name="Year 9 Maths")
    assign_object_role(educator_user, organisation_a, "organisation_admin")
    assign_object_role(educator_user, organisation_b, "organisation_admin")
    ada = LearnerFactory(
        organisation=organisation_a,
        user=UserFactory(
            first_name="Ada", last_name="Lovelace", email="ada@example.com"
        ),
    )
    CohortMembershipFactory(learner=ada, cohort=year_nine)
    for first_name in ("Al", "Christopher"):
        LearnerFactory(
            organisation=organisation_a,
            user=UserFactory(first_name=first_name, last_name="Lovelace"),
        )

    # The live region sits outside #main-content, so an ordinary swap leaves
    # that very element in place for assistive technology to keep watching.
    page.goto(interface_url(live_server, organisation_a.slug, "cohorts"))
    announcer = page.locator("#scope-announcer")
    expect(announcer).to_have_count(1)
    page.locator('a[href$="/learners"]').click()
    expect(page).to_have_url(
        interface_url(live_server, organisation_a.slug, "learners")
    )
    expect(announcer).to_have_count(1)

    # Opening the switcher from the keyboard puts focus on the checked option.
    page.get_by_role("button", name="Switch organisation").focus()
    page.keyboard.press("Enter")
    expect(page.get_by_role("menuitemradio", name="Org A")).to_be_focused()
    page.keyboard.press("Tab")
    expect(page.get_by_role("menuitemradio", name="Org B")).to_be_focused()
    page.keyboard.press("Enter")
    expect(page).to_have_url(
        interface_url(live_server, organisation_b.slug, "learners")
    )
    # The same element, now carrying the new text: announced in place.
    expect(announcer).to_have_count(1)
    expect(announcer).to_have_text("Now viewing Org B")

    # Create a cohort.
    page.goto(interface_url(live_server, organisation_a.slug, "cohorts"))
    page.get_by_role("button", name="Create Cohort").click()
    modal = page.locator("#app-modal")
    modal.get_by_label("Name").fill("Old Name")
    modal.get_by_role("button", name="Save", exact=True).click()
    expect(modal).to_be_hidden()
    created = Cohort.objects.get(name="Old Name")
    assign_perm("freedom_ls_learner_management.change_cohort", educator_user, created)
    assign_perm("freedom_ls_learner_management.delete_cohort", educator_user, created)

    # Edit its name: the modal closes and the heading and tab title update.
    page.goto(interface_url(live_server, organisation_a.slug, f"cohorts/{created.pk}"))
    page.get_by_role("button", name="Edit").click()
    # Scoped: the dialog's own aria-labelledby also matches get_by_label.
    modal.locator("#app-modal-body").get_by_label("Name").fill("New Name")
    page.get_by_role("button", name="Save", exact=True).click()
    expect(modal).to_be_hidden()
    expect(page.locator("#instance-title")).to_have_text("New Name")
    expect(page).to_have_title(re.compile(r"^New Name — "))

    # Learner quick view.
    page.goto(interface_url(live_server, organisation_a.slug, "learners"))
    _assert_quick_view_triggers_line_up(page)
    ada_trigger = page.get_by_role("link", name="Quick view: Ada", exact=True)
    drawer = _open_drawer(page, ada_trigger)
    expect(page.locator("#quick-view-subtitle")).to_have_text("ada@example.com")
    expect(page.locator("#quick-view-body")).to_contain_text("Year 9 Maths")
    expect(page.locator("#quick-view-body")).not_to_have_attribute("aria-busy", "true")
    title = page.locator("#quick-view-title")
    expect(title).to_have_text("Ada Lovelace")

    # The drawer's title is still the learner's name after a reopen.
    page.keyboard.press("Escape")
    expect(drawer).to_be_hidden()
    ada_trigger.click()
    expect(drawer).to_be_visible()
    expect(title).to_have_text("Ada Lovelace")

    # A dropdown opened over the drawer is its own layer: one Esc closes the
    # dropdown and leaves the drawer open, a second closes the drawer.
    switcher_button = page.get_by_role("button", name="Switch organisation")
    switcher_button.click()
    expect(switcher_button).to_have_attribute("aria-expanded", "true")
    page.keyboard.press("Escape")
    expect(switcher_button).to_have_attribute("aria-expanded", "false")
    # The close transition keeps the drawer on screen for a moment after
    # close() runs, so only the [open] attribute says whether it is still open.
    expect(drawer).to_have_attribute("open", "")
    page.keyboard.press("Escape")
    expect(drawer).not_to_have_attribute("open", "")

    # A learnerChanged event refetches the drawer only for the learner shown.
    ada_trigger.click()
    expect(drawer).to_have_attribute("open", "")
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
            str(ada.pk),
        )

    # Open leads to the learner's own page.
    page.locator("#quick-view-open").click()
    expect(page).to_have_url(
        interface_url(live_server, organisation_a.slug, f"learners/{ada.pk}")
    )

    # Delete the cohort from its settings tab without a failing request: the
    # page being left must not refetch panels for the cohort that no longer
    # exists.
    failed: list[str] = []

    def record_failure(response: Response) -> None:
        if response.status >= 400:
            failed.append(f"{response.status} {response.url}")

    page.goto(
        interface_url(
            live_server, organisation_a.slug, f"cohorts/{created.pk}/__tabs/settings"
        )
    )
    page.on("response", record_failure)
    page.get_by_role("button", name="Delete", exact=True).click()
    # Scoped: the trigger with the same name sits behind the dialog.
    modal.get_by_role("button", name="Delete", exact=True).click()
    expect(modal).to_be_hidden()
    expect(page).to_have_url(interface_url(live_server, organisation_a.slug, "cohorts"))
    expect(page.get_by_role("link", name="Year 9 Maths", exact=True)).to_be_visible()
    assert not Cohort.objects.filter(pk=created.pk).exists()
    page.remove_listener("response", record_failure)
    assert failed == []

    # A grant revoked while the create modal is open denies the submit. The
    # cohort_viewer grant keeps the organisation reachable afterwards.
    assign_object_role(educator_user, year_nine, "cohort_viewer")
    page.goto(interface_url(live_server, organisation_a.slug, "cohorts"))
    page.get_by_role("button", name="Create Cohort").click()
    page.locator("#app-modal").get_by_label("Name").fill("Should never exist")
    remove_object_role(educator_user, organisation_a, "organisation_admin")
    modal.get_by_role("button", name="Save", exact=True).click()
    heading = page.get_by_role(
        "heading", name="You can't use “Create Cohort” here any more"
    )
    expect(heading).to_be_visible()
    expect(page.get_by_text("Your role doesn't allow it.")).to_be_visible()
    expect(page.locator("#app-modal").get_by_label("Name")).to_have_count(0)
    close_button = page.get_by_role("button", name="Close").last
    expect(close_button).to_be_visible()
    close_button.click()
    expect(heading).to_be_hidden()
    assert not Cohort.objects.filter(name="Should never exist").exists()

    # A cohort leaving scope while its delete dialog is open says so. This
    # one carries no cohort grant, so it leaves with organisation_admin.
    assign_object_role(educator_user, organisation_a, "organisation_admin")
    leaving = CohortFactory(organisation=organisation_a, name="Leaving Scope")
    page.goto(
        interface_url(
            live_server, organisation_a.slug, f"cohorts/{leaving.pk}/__tabs/settings"
        )
    )
    page.get_by_role("button", name="Delete").first.click()
    dialog_delete = page.get_by_role("dialog").get_by_role("button", name="Delete")
    expect(dialog_delete).to_be_visible()
    remove_object_role(educator_user, organisation_a, "organisation_admin")
    dialog_delete.click()
    heading = page.get_by_role("heading", name="This is no longer available")
    expect(heading).to_be_visible()
    expect(page.get_by_text("Are you sure you want to delete")).to_be_hidden()
    close_button = page.get_by_role("button", name="Close").last
    expect(close_button).to_be_visible()
    close_button.click()
    expect(heading).to_be_hidden()
    assert Cohort.objects.filter(pk=leaving.pk).exists()


def test_quick_view_and_learners_list_layout_across_viewports(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation = OrganisationFactory(name="Org A")
    CohortFactory(organisation=organisation, name="Year 9 Maths")
    assign_object_role(educator_user, organisation, "organisation_admin")
    for first_name in ("Al", "Christopher"):
        LearnerFactory(
            organisation=organisation,
            user=UserFactory(first_name=first_name, last_name="Lovelace"),
        )
    LearnerFactory(
        organisation=organisation,
        user=UserFactory(
            first_name=_LONG_NAME,
            last_name=_LONG_NAME,
            email=f"{_LONG_NAME.lower()}@example.com",
        ),
    )
    LearnerFactory.create_batch(
        51, organisation=organisation, user__first_name="Learner"
    )
    learners_url = interface_url(live_server, organisation.slug, "learners")
    cohorts_url = interface_url(live_server, organisation.slug, "cohorts")

    # The list has no horizontal scroll and aligned triggers at every width.
    # The table and the card list both render the long name and one of them
    # is hidden at any width, so only the visible match counts; .first because
    # first and last name are the same string and a card shows it twice.
    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(learners_url)
        long_name = (
            page.locator("#learners-table")
            .get_by_text(_LONG_NAME)
            .filter(visible=True)
            .first
        )
        expect(long_name).to_be_visible()
        assert_no_horizontal_overflow(page)
        _assert_quick_view_triggers_line_up(page)

    # Docked, the drawer starts below the header and the page makes room, so
    # the list's actions and every table column stay reachable. The page's
    # title and table do not move when the drawer opens or closes.
    for width in _DOCKED_WIDTHS:
        page.set_viewport_size({"width": width, "height": 900})
        page.goto(cohorts_url)
        title = page.locator("#main-content h1")
        table = page.locator("#main-content table")
        at_rest = (_box(title)["x"], _box(table)["x"])

        drawer = _open_drawer(
            page, page.get_by_role("link", name="Quick view: Year 9 Maths")
        )
        expect(page.locator("dialog:modal")).to_have_count(0)
        drawer_box = _box(drawer)
        header_box = _box(page.locator("header.header"))
        create_button = page.get_by_role("button", name="Create Cohort")
        create_box = _box(create_button)
        table_box = _box(table)
        assert drawer_box["y"] >= header_box["y"] + header_box["height"] - 1
        assert create_box["x"] + create_box["width"] <= drawer_box["x"]
        assert table_box["x"] + table_box["width"] <= drawer_box["x"]
        assert (_box(title)["x"], _box(table)["x"]) == at_rest

        create_button.click()
        expect(page.locator("#app-modal")).to_be_visible()
        page.keyboard.press("Escape")
        expect(page.locator("#app-modal")).to_be_hidden()

        drawer.get_by_role("button", name="Close").click()
        expect(drawer).to_be_hidden()
        assert (_box(title)["x"], _box(table)["x"]) == at_rest

    # The drawer's top offset must follow the header's height after the page
    # widens from a phone without a reload, and the numbered pagination
    # must wrap inside the narrowed card beside the docked drawer.
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(learners_url)
    page.set_viewport_size({"width": 1400, "height": 900})
    drawer = _open_drawer(
        page, page.get_by_role("link", name="Quick view: Learner", exact=True).first
    )
    header_box = _box(page.locator("header.header"))
    assert _box(drawer)["y"] >= header_box["y"] + header_box["height"] - 1
    next_link = page.get_by_role("link", name="Next", exact=True)
    expect(next_link).to_be_visible()
    next_box = _box(next_link)
    assert next_box["x"] + next_box["width"] <= _box(drawer)["x"]
