"""The educator cohort page on a phone.

The header's badge and stats and the tab row must fit the viewport without a
horizontal scroll, which only a real browser proves.
"""

from __future__ import annotations

import re
from typing import cast

import pytest
from allauth.account.models import EmailAddress
from playwright.sync_api import Page, expect

from django.contrib.auth.base_user import AbstractBaseUser
from django.urls import reverse

from freedom_ls.learner_management.factories import CohortFactory, LearnerFactory
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.tests.playwright_fixtures import _LOGGED_IN_PASSWORD, sign_in

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
    sign_in(page, live_server, mobile_educator)
    return page


def test_cohort_detail_mobile_flow(
    live_server,
    mobile_educator_page: Page,
    mobile_educator: AbstractBaseUser,
) -> None:
    """At 375px the cohort header carries no badge or stats, the tabs are
    visible, the page does not overflow horizontally, and the History tab opens
    with the active tab in view of the scrolling strip."""
    page = mobile_educator_page
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
    page.goto(f"{live_server.url}{path}")

    expect(page.locator("#instance-title")).to_have_text("Evening group")
    header = page.locator("#instance-title").locator(
        "xpath=ancestor::div[contains(@class, 'justify-between')][1]"
    )
    # Active is the default state and the tabs count learners and courses,
    # so the header carries neither a badge nor stats.
    expect(
        header.get_by_text("Active", exact=True), "header shows a badge"
    ).to_have_count(0)
    expect(
        header.get_by_text("Learners", exact=True), "header shows stats"
    ).to_have_count(0)
    tabs = page.get_by_role("navigation", name="Cohort sections")
    expect(tabs.get_by_role("link", name=re.compile("^Learners"))).to_be_visible()
    expect(tabs.get_by_role("link", name="Overview")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth") <= _PHONE_WIDTH, (
        "cohort page overflows horizontally at 375px"
    )

    # The strip scrolls sideways on a phone, and the last tabs start off screen.
    history_path = reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": organisation.slug,
            "path_string": f"cohorts/{cohort.pk}/__tabs/history",
        },
    )
    page.goto(f"{live_server.url}{history_path}")
    active = tabs.locator("a[aria-current='page']")
    expect(active).to_have_text("History")
    # Short of 1 only by the sub-pixel rounding of the strip's own edge.
    expect(active, "History tab not in view of the tab strip").to_be_in_viewport(
        ratio=0.99
    )
