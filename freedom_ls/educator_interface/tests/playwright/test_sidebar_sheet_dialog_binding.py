"""The sidebar <dialog> in a real browser.

The educator layout's sidebar and a panel_framework table's mobile "Filter &
sort" sheet are two separate ``x-data="sidePanel"`` Alpine components, one
nested inside the other's DOM subtree. Only a real browser proves each
instance's ``$refs.panelDialog`` resolves to its *own* ``<dialog>`` rather
than the nearer one in the shared Alpine scope — the Django test client never
runs Alpine at all.

Three more things only a browser shows: dialog.show() moves focus into the
docked sidebar unless the controller puts it back, the navigation sheet's
slide is a CSS transition that reduced motion must switch off, and widening
the window while the sheet is open re-docks the sidebar through the dialog's
asynchronous close event.
"""

from __future__ import annotations

import pytest
from allauth.account.models import EmailAddress
from playwright.sync_api import Page, expect

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.learner_management.factories import CohortFactory, LearnerFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role
from freedom_ls.tests.playwright_fixtures import _LOGGED_IN_PASSWORD, _login_via_ui

from .helpers import interface_url

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

# Narrow enough that the sidebar is the modal sheet rather than the docked
# desktop column (the controller docks the panel from 1024px up).
_MOBILE_VIEWPORT = {"width": 390, "height": 844}


@pytest.fixture
def mobile_educator(db, live_server_site, mock_site_context) -> User:
    """A fresh, email-verified staff user."""
    user: User = UserFactory(staff=True, password=_LOGGED_IN_PASSWORD)
    EmailAddress.objects.get_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )
    return user


@pytest.fixture
def mobile_educator_page(page: Page, live_server, mobile_educator: User) -> Page:
    """A Playwright Page at a phone viewport, logged in as mobile_educator."""
    page.set_viewport_size(_MOBILE_VIEWPORT)
    _login_via_ui(page, live_server, str(mobile_educator.email), _LOGGED_IN_PASSWORD)
    return page


def test_nav_button_opens_navigation_not_the_tables_filter_sheet(
    live_server,
    mobile_educator_page: Page,
    mobile_educator: User,
) -> None:
    page = mobile_educator_page
    organisation = OrganisationFactory()
    assign_object_role(mobile_educator, organisation, "organisation_admin")
    LearnerFactory(user=UserFactory(), organisation=organisation)

    path = reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation.slug, "path_string": "learners"},
    )
    page.goto(f"{live_server.url}{path}")

    nav_sheet = page.locator("dialog[aria-label='Navigation']")
    filter_sheet = page.locator("dialog[aria-label='Filter and sort']")
    expect(nav_sheet).to_be_hidden()
    expect(filter_sheet).to_be_hidden()

    page.get_by_role("button", name="Open navigation panel").click()

    # The bug swaps these: the button opens the table's Filter & sort sheet
    # (bound via the wrong dialog ref) instead of the sidebar navigation.
    expect(nav_sheet).to_be_visible()
    expect(filter_sheet).to_be_hidden()
    expect(nav_sheet.locator("#sidebar-nav")).to_be_visible()


_DESKTOP = {"width": 1442, "height": 900}
_PHONE = {"width": 392, "height": 850}


def _cohorts_url(live_server, educator_user: User) -> str:
    organisation = OrganisationFactory(name="Org A")
    CohortFactory(organisation=organisation, name="Year 9 Maths")
    assign_object_role(educator_user, organisation, "organisation_admin")
    return interface_url(live_server, organisation.slug, "cohorts")


def test_the_first_tab_on_a_desktop_page_reaches_the_site_header(
    live_server, educator_logged_in_page: Page, educator_user: User
) -> None:
    page = educator_logged_in_page
    page.set_viewport_size(_DESKTOP)

    page.goto(_cohorts_url(live_server, educator_user))
    expect(page.locator("dialog[aria-label='Navigation']")).to_be_visible()

    assert page.evaluate("document.activeElement === document.body")
    page.keyboard.press("Tab")

    focused_in_header = page.evaluate(
        "document.querySelector('header.header').contains(document.activeElement)"
    )
    assert focused_in_header


def test_the_navigation_sheet_does_not_slide_under_reduced_motion(
    live_server, educator_logged_in_page: Page, educator_user: User
) -> None:
    page = educator_logged_in_page
    page.set_viewport_size(_PHONE)
    page.emulate_media(reduced_motion="reduce")

    page.goto(_cohorts_url(live_server, educator_user))
    page.get_by_role("button", name="Open navigation panel").click()

    sheet = page.locator("dialog[aria-label='Navigation']")
    expect(sheet).to_be_visible()
    expect(sheet).to_have_css("transition-duration", "0s")


def test_widening_past_lg_with_the_sheet_open_docks_the_sidebar(
    live_server, educator_logged_in_page: Page, educator_user: User
) -> None:
    page = educator_logged_in_page
    page.set_viewport_size(_PHONE)
    page.goto(_cohorts_url(live_server, educator_user))
    page.get_by_role("button", name="Open navigation panel").click()
    sheet = page.locator("dialog[aria-label='Navigation']")
    expect(sheet).to_be_visible()
    expect(page.locator("dialog[aria-label='Navigation']:modal")).to_have_count(1)

    page.set_viewport_size(_DESKTOP)

    expect(sheet).to_be_visible()
    expect(page.locator("dialog[aria-label='Navigation']:modal")).to_have_count(0)
    sidebar_box = sheet.bounding_box()
    main_box = page.locator("#main-content").bounding_box()
    assert sidebar_box is not None
    assert main_box is not None
    assert sidebar_box["width"] >= 200
    assert main_box["width"] >= 800
    assert main_box["x"] >= sidebar_box["x"] + sidebar_box["width"]


def test_the_navigation_sheet_has_rounded_top_corners(
    live_server, educator_logged_in_page: Page, educator_user: User
) -> None:
    page = educator_logged_in_page
    page.set_viewport_size(_PHONE)

    page.goto(_cohorts_url(live_server, educator_user))
    page.get_by_role("button", name="Open navigation panel").click()

    body = page.locator("dialog[aria-label='Navigation'] .side-panel-body")
    expect(body).to_be_visible()
    expect(body).to_have_css("border-top-left-radius", "16px")
    expect(body).to_have_css("border-top-right-radius", "16px")
