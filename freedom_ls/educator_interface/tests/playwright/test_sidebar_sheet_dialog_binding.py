"""The mobile nav button on a page with a panel_framework table.

The educator layout's sidebar and a panel_framework table's mobile "Filter &
sort" sheet are two separate ``x-data="sidePanel"`` Alpine components, one
nested inside the other's DOM subtree. Only a real browser proves each
instance's ``$refs.panelDialog`` resolves to its *own* ``<dialog>`` rather
than the nearer one in the shared Alpine scope — the Django test client never
runs Alpine at all.
"""

from __future__ import annotations

import pytest
from allauth.account.models import EmailAddress
from playwright.sync_api import Page, expect

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role
from freedom_ls.tests.playwright_fixtures import _LOGGED_IN_PASSWORD, _login_via_ui

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
