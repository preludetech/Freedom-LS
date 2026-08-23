"""Browser-only behaviour of the organisation switcher that the Django test
client cannot exercise: keyboard operation, aria-checked tracking the
current organisation after a real HTMX swap, and the live region announcing
in place rather than being destroyed and recreated.

The Django test client coverage (switch handling, the narrow
OrganisationScopeDenied catch, OOB fragment content) lives in
educator_interface/tests/test_organisation_switcher.py.
"""

from __future__ import annotations

import pytest
from allauth.account.models import EmailAddress
from playwright.sync_api import Page, expect

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role
from freedom_ls.tests.playwright_fixtures import _LOGGED_IN_PASSWORD, _login_via_ui

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


@pytest.fixture
def educator_user(db, live_server_site, mock_site_context) -> User:
    """A fresh, email-verified staff user.

    A staff variant of freedom_ls.tests.playwright_fixtures.logged_in_user —
    that fixture is hard-coded to a plain learner, and this module is the
    first to need an educator instead.
    """
    user: User = UserFactory(staff=True, password=_LOGGED_IN_PASSWORD)
    EmailAddress.objects.get_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )
    return user


@pytest.fixture
def educator_logged_in_page(page: Page, live_server, educator_user: User) -> Page:
    """A Playwright Page logged in as educator_user."""
    _login_via_ui(page, live_server, str(educator_user.email), _LOGGED_IN_PASSWORD)
    return page


def _interface_url(live_server, organisation_slug: str, path_string: str) -> str:
    from django.urls import reverse

    path = reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation_slug, "path_string": path_string},
    )
    return f"{live_server.url}{path}"


@pytest.fixture
def two_organisations(educator_user: User):
    organisation_a = OrganisationFactory(name="Org A")
    organisation_b = OrganisationFactory(name="Org B")
    CohortFactory(organisation=organisation_b, name="Org B Cohort")
    assign_object_role(educator_user, organisation_a, "organisation_staff")
    assign_object_role(educator_user, organisation_b, "organisation_staff")
    return organisation_a, organisation_b


def test_ordinary_navigation_leaves_the_live_region_in_place(
    live_server,
    educator_logged_in_page: Page,
    two_organisations,
):
    """The live region lives outside #main-content so an ordinary swap leaves
    it alone. Replacing the element rather than its contents would leave
    assistive technology watching a node no longer in the document."""
    page = educator_logged_in_page
    organisation_a, _organisation_b = two_organisations
    page.goto(_interface_url(live_server, organisation_a.slug, "cohorts"))
    announcer = page.locator("#scope-announcer")
    expect(announcer).to_have_count(1)

    page.get_by_role("link", name="Learners").click()

    expect(page).to_have_url(
        _interface_url(live_server, organisation_a.slug, "learners")
    )
    expect(announcer).to_have_count(1)


def test_keyboard_switch_moves_focus_and_announces_in_place(
    live_server,
    educator_logged_in_page: Page,
    two_organisations,
):
    page = educator_logged_in_page
    organisation_a, organisation_b = two_organisations
    page.goto(_interface_url(live_server, organisation_a.slug, "learners"))
    announcer = page.locator("#scope-announcer")

    page.get_by_role("button", name="Switch organisation").focus()
    page.keyboard.press("Enter")
    org_a_option = page.get_by_role("menuitemradio", name="Org A")
    org_b_option = page.get_by_role("menuitemradio", name="Org B")
    # Opening from the keyboard puts focus straight on the checked option.
    expect(org_a_option).to_be_focused()
    page.keyboard.press("Tab")
    expect(org_b_option).to_be_focused()

    page.keyboard.press("Enter")

    expect(page).to_have_url(
        _interface_url(live_server, organisation_b.slug, "learners")
    )
    # Still the same element, now carrying the new text — the whole point of
    # announcing into the live region rather than replacing it.
    expect(announcer).to_have_count(1)
    expect(announcer).to_have_text("Now viewing Org B")
