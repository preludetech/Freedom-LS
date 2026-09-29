"""The denial fragment as it actually renders in a browser: an htmx swap
replacing the still-open Create Cohort modal with the denial modal, not
just the 403 status a Django test client can already assert on.

The Django test client coverage (403 status, denial copy, no cohort
created) lives in educator_interface/tests/test_denied_experience.py.
"""

from __future__ import annotations

import pytest
from allauth.account.models import EmailAddress
from playwright.sync_api import Page, expect

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.utils import (
    assign_object_role,
    remove_object_role,
)
from freedom_ls.tests.playwright_fixtures import _LOGGED_IN_PASSWORD, _login_via_ui

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


@pytest.fixture
def educator_user(db, live_server_site, mock_site_context) -> User:
    """A fresh, email-verified staff user."""
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
def organisation_with_a_lapsing_admin(educator_user: User) -> Organisation:
    """An organisation educator_user administers, plus a cohort they hold
    cohort_viewer on -- so the organisation stays reachable once
    organisation_admin is removed mid-test."""
    organisation: Organisation = OrganisationFactory(name="Lapsing Org")
    cohort = CohortFactory(organisation=organisation)
    assign_object_role(educator_user, organisation, "organisation_admin")
    assign_object_role(educator_user, cohort, "cohort_viewer")
    return organisation


def test_a_grant_revoked_while_the_create_cohort_modal_is_open_denies_the_submit(
    live_server,
    educator_logged_in_page: Page,
    educator_user: User,
    organisation_with_a_lapsing_admin: Organisation,
):
    organisation = organisation_with_a_lapsing_admin
    page = educator_logged_in_page
    page.goto(_interface_url(live_server, organisation.slug, "cohorts"))
    page.get_by_role("button", name="Create Cohort").click()
    page.get_by_label("Name").fill("Should never exist")

    remove_object_role(educator_user, organisation, "organisation_admin")
    page.get_by_role("button", name="Save", exact=True).click()

    heading = page.get_by_role(
        "heading", name="You can't use “Create Cohort” here any more"
    )
    expect(heading).to_be_visible()
    expect(page.get_by_text("Your role doesn't allow it.")).to_be_visible()
    expect(page.get_by_label("Name")).to_have_count(0)
    close_button = page.get_by_role("button", name="Close").last
    expect(close_button).to_be_visible()

    close_button.click()

    expect(heading).to_be_hidden()
