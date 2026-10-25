"""Browser flow for an educator whose last role in an organisation is removed
while one of its pages is open.

The server already answers every later request with a 404; test_views.py and
test_denied_experience.py cover that. What only a browser shows is what htmx
does with a bare 404: without help it drops it and the page sits unchanged.
These flows expect the page to land on the not-found page a fresh visit would
show, whether the request came from a navigation link or from the confirm
button of an open dialog.
"""

from __future__ import annotations

from typing import cast

import pytest
from playwright.sync_api import Page, expect

from django.contrib.auth.base_user import AbstractBaseUser

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.utils import deactivate_object_role
from freedom_ls.tests.playwright_helpers import QA_VIEWPORTS

from .helpers import interface_url

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_NOT_FOUND_HEADING = "We cannot find that page"


def _organisation_run_by(educator_user: AbstractBaseUser) -> Organisation:
    """An organisation where `educator_user` holds organisation_admin and
    nothing else, so removing that one role removes all access."""
    organisation = cast(Organisation, OrganisationFactory(name="Org A"))
    grantor = UserFactory(superuser=True)
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    return organisation


def test_a_navigation_click_after_losing_access_lands_on_the_not_found_page(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation = _organisation_run_by(educator_user)
    # Wide enough that the sidebar docks as a column instead of a sheet.
    page.set_viewport_size(QA_VIEWPORTS[2])
    page.goto(interface_url(live_server, organisation.slug, "members"))
    # The link's name also carries the section's count, so no exact match.
    cohorts_link = page.locator("#sidebar-nav").get_by_role("link", name="Cohorts")
    expect(cohorts_link).to_be_visible()

    deactivate_object_role(educator_user, organisation, "organisation_admin")
    cohorts_link.click()

    expect(page.get_by_role("heading", name=_NOT_FOUND_HEADING)).to_be_visible()


def test_a_confirm_in_an_open_dialog_after_losing_access_lands_on_the_not_found_page(
    live_server,
    educator_logged_in_page: Page,
    educator_user: AbstractBaseUser,
) -> None:
    page = educator_logged_in_page
    organisation = _organisation_run_by(educator_user)
    cohort = CohortFactory(organisation=organisation, name="Alpha Cohort")
    viewer = UserFactory(
        email="viewer@example.com", first_name="Vee", last_name="Viewer"
    )
    assign_role(UserFactory(superuser=True), viewer, "cohort_viewer", cohort)
    page.goto(interface_url(live_server, organisation.slug, "members"))
    row = page.locator("#main-content").get_by_role("row").filter(has_text="Vee Viewer")
    row.get_by_role("button", name="Remove", exact=True).click()
    modal = page.locator("#app-modal")
    expect(modal.get_by_text("They lose")).to_be_visible()

    deactivate_object_role(educator_user, organisation, "organisation_admin")
    modal.get_by_role("button", name="Remove", exact=True).click()

    expect(page.get_by_role("heading", name=_NOT_FOUND_HEADING)).to_be_visible()
