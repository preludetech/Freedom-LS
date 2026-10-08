"""The educator cohort page on a phone.

The header's badge and stats and the tab row must fit the viewport without a
horizontal scroll, which only a real browser proves.
"""

from __future__ import annotations

from typing import cast

import pytest
from allauth.account.models import EmailAddress
from playwright.sync_api import Page, expect

from django.contrib.auth.base_user import AbstractBaseUser
from django.urls import reverse

from freedom_ls.learner_management.factories import CohortFactory, LearnerFactory
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.tests.playwright_fixtures import _LOGGED_IN_PASSWORD, _login_via_ui

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_PHONE_WIDTH = 375


@pytest.fixture
def mobile_educator(db, live_server_site, mock_site_context) -> AbstractBaseUser:
    """A fresh, email-verified staff user."""
    user = cast(
        AbstractBaseUser,
        LearnerFactory(user__staff=True, user__password=_LOGGED_IN_PASSWORD).user,
    )
    EmailAddress.objects.get_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )
    return user


@pytest.fixture
def mobile_educator_page(
    page: Page, live_server, mobile_educator: AbstractBaseUser
) -> Page:
    """A Playwright Page at a phone viewport, logged in as mobile_educator."""
    page.set_viewport_size({"width": _PHONE_WIDTH, "height": 812})
    _login_via_ui(page, live_server, str(mobile_educator.email), _LOGGED_IN_PASSWORD)
    return page


def test_cohort_page_header_and_tabs_fit_a_phone(
    live_server,
    mobile_educator_page: Page,
    mobile_educator: AbstractBaseUser,
) -> None:
    organisation = OrganisationFactory()
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, mobile_educator, "organisation_admin", organisation)
    cohort = CohortFactory(organisation=organisation, name="Evening group")

    path = reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": organisation.slug,
            "path_string": f"cohorts/{cohort.pk}",
        },
    )
    mobile_educator_page.goto(f"{live_server.url}{path}")

    expect(mobile_educator_page.locator("#instance-title")).to_have_text(
        "Evening group"
    )
    header = mobile_educator_page.locator("#instance-title").locator(
        "xpath=ancestor::div[contains(@class, 'justify-between')][1]"
    )
    expect(header.get_by_text("Active", exact=True)).to_be_visible()
    expect(header.get_by_text("Learners", exact=True)).to_be_visible()
    expect(header.get_by_text("Courses", exact=True)).to_be_visible()
    tabs = mobile_educator_page.get_by_role("navigation", name="Cohort sections")
    expect(tabs.get_by_role("link", name="Overview")).to_be_visible()
    assert (
        mobile_educator_page.evaluate("document.documentElement.scrollWidth")
        <= _PHONE_WIDTH
    )
