"""The educator Learners list on a phone.

Long names must not push the page wider than the viewport once the table
switches to cards below md — only a real browser proves that reliably.
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

_PHONE_VIEWPORT = {"width": 390, "height": 844}
_LONG_NAME = "Balasubramaniamnathan" * 3


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
    page.set_viewport_size(_PHONE_VIEWPORT)
    _login_via_ui(page, live_server, str(mobile_educator.email), _LOGGED_IN_PASSWORD)
    return page


def test_learners_list_has_no_horizontal_scroll_on_phone(
    live_server,
    mobile_educator_page: Page,
    mobile_educator: User,
) -> None:
    organisation = OrganisationFactory()
    assign_object_role(mobile_educator, organisation, "organisation_staff")
    LearnerFactory(
        user=UserFactory(
            first_name=_LONG_NAME,
            last_name=_LONG_NAME,
            email=f"{_LONG_NAME.lower()}@example.com",
        ),
        organisation=organisation,
    )

    path = reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation.slug, "path_string": "learners"},
    )
    mobile_educator_page.goto(f"{live_server.url}{path}")

    # The desktop table (hidden below md) also renders the learner's name, so
    # scope to the visible card list specifically. .first: the same long
    # string is both the first and last name here, so the card shows it
    # twice (primary title, secondary meta line).
    expect(
        mobile_educator_page.locator("#learners-table ul").get_by_text(_LONG_NAME).first
    ).to_be_visible()

    overflows = mobile_educator_page.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth"
    )
    assert overflows is False
