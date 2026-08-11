"""The organisation switcher driven from the mobile navigation sheet.

Below the ``lg`` breakpoint the sidebar is a modal ``<dialog>`` opened with
``showModal()``, so switching organisation from it has to dismiss the sheet
as well as swap the content — and it has to do that without leaving the
address bar and the content disagreeing when the user presses Back. Neither
half is observable outside a real browser: the Django test client never runs
the sheet controller, and ``<dialog>`` modality plus the session history are
browser state.

Desktop / keyboard behaviour of the same switcher lives in
test_organisation_switcher.py.
"""

from __future__ import annotations

import pytest
from allauth.account.models import EmailAddress
from playwright.sync_api import Page, expect

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role
from freedom_ls.student_management.factories import CohortFactory
from freedom_ls.tests.playwright_fixtures import _LOGGED_IN_PASSWORD, _login_via_ui

pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

# Narrow enough that the sidebar is the modal sheet rather than the docked
# desktop column (the controller docks the panel from 1024px up).
_MOBILE_VIEWPORT = {"width": 375, "height": 750}


@pytest.fixture
def mobile_educator(db, live_server_site, mock_site_context, mocker) -> User:
    """A fresh, email-verified staff user.

    Site.objects.get_current is patched so assign_object_role, called from the
    test's own thread, resolves the same Site mock_site_context set up.
    """
    mocker.patch(
        "django.contrib.sites.models.SiteManager.get_current",
        return_value=mock_site_context,
    )
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


def _interface_url(live_server, organisation_slug: str, path_string: str) -> str:
    from django.urls import reverse

    path = reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation_slug, "path_string": path_string},
    )
    return f"{live_server.url}{path}"


def test_switching_from_the_mobile_sheet_closes_it_and_keeps_url_and_content_together(
    live_server,
    mobile_educator_page: Page,
    mobile_educator: User,
):
    page = mobile_educator_page
    organisation_a = OrganisationFactory(name="Org A")
    organisation_b = OrganisationFactory(name="Org B")
    CohortFactory(organisation=organisation_a, name="Alpha Cohort")
    CohortFactory(organisation=organisation_b, name="Beta Cohort")
    assign_object_role(mobile_educator, organisation_a, "organisation_staff")
    assign_object_role(mobile_educator, organisation_b, "organisation_staff")

    page.goto(_interface_url(live_server, organisation_a.slug, "cohorts"))

    # The sheet is the <dialog> itself, and its open state is what regressed,
    # so this test asserts on that element rather than on its contents.
    sheet = page.locator("dialog[aria-label='Navigation']")
    expect(sheet).to_be_hidden()

    page.get_by_role("button", name="Open navigation panel").click()
    expect(sheet).to_be_visible()

    page.get_by_role("button", name="Switch organisation").click()
    page.get_by_role("menuitemradio", name="Org B").click()

    expect(page).to_have_url(
        _interface_url(live_server, organisation_b.slug, "cohorts")
    )
    expect(sheet).to_be_hidden()
    expect(page.locator("#organisation-switcher")).to_contain_text("Org B")
    expect(page.get_by_role("link", name="Beta Cohort")).to_be_visible()
    expect(page.get_by_role("link", name="Alpha Cohort")).to_have_count(0)

    # Back must land on the organisation switched away from with its content
    # restored — the sheet's own history entry must not strand the address bar
    # on one organisation while the page shows the other.
    page.go_back()
    expect(page).to_have_url(
        _interface_url(live_server, organisation_a.slug, "cohorts")
    )
    expect(sheet).to_be_hidden()
    expect(page.locator("#organisation-switcher")).to_contain_text("Org A")
    expect(page.get_by_role("link", name="Alpha Cohort")).to_be_visible()
