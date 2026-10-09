"""The messaging config admin changelist on a phone.

Below the ``lg`` breakpoint unfold turns each changelist row into a card whose
cells are fixed at 45px with ``overflow: hidden``, so any value that wraps past
one line is cut off. Whether a cell clips is a layout fact only a real browser
can settle, so this lives in Playwright rather than the Django client.
"""

from __future__ import annotations

import pytest
from allauth.account.models import EmailAddress
from playwright.sync_api import Page, expect

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.messaging_policy.factories import (
    LearnerMessagingConfigFactory,
    SiteMessagingConfigFactory,
)
from freedom_ls.tests.playwright_fixtures import _LOGGED_IN_PASSWORD, _login_via_ui

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_PHONE_VIEWPORT = {"width": 375, "height": 812}

_CLIPPED_CELLS_JS = """
() => Array.from(document.querySelectorAll("#result_list td, #result_list th"))
    .filter((cell) => cell.scrollHeight > cell.clientHeight)
    .map((cell) => cell.textContent.trim())
"""


@pytest.fixture
def admin_user(db, live_server_site, mock_site_context) -> User:
    """A fresh, email-verified superuser."""
    user: User = UserFactory(superuser=True, password=_LOGGED_IN_PASSWORD)
    EmailAddress.objects.get_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )
    return user


@pytest.fixture
def phone_admin_page(page: Page, live_server, admin_user: User) -> Page:
    """A Playwright Page at a phone viewport, logged in as admin_user."""
    page.set_viewport_size(_PHONE_VIEWPORT)
    _login_via_ui(page, live_server, str(admin_user.email), _LOGGED_IN_PASSWORD)
    return page


def test_changelist_card_cells_grow_to_fit_wrapped_values(
    live_server, phone_admin_page: Page
) -> None:
    learner = LearnerFactory(
        user=UserFactory(email="a.rather.long.learner.address@example.com")
    )
    config = LearnerMessagingConfigFactory(learner=learner)

    phone_admin_page.goto(
        f"{live_server.url}"
        f"{reverse('admin:freedom_ls_messaging_policy_learnermessagingconfig_changelist')}"
    )

    expect(phone_admin_page.get_by_text(str(config), exact=True)).to_be_visible()

    assert phone_admin_page.evaluate(_CLIPPED_CELLS_JS) == []


def test_offered_roles_options_are_comfortable_tap_targets(
    live_server, phone_admin_page: Page
) -> None:
    """The offered-roles checkboxes were bare native inputs stacked 17px apart."""
    config = SiteMessagingConfigFactory()

    phone_admin_page.goto(
        f"{live_server.url}"
        f"{reverse('admin:freedom_ls_messaging_policy_sitemessagingconfig_change', args=[config.pk])}"
    )

    first = phone_admin_page.get_by_label("Use the settings default")
    second = phone_admin_page.get_by_label("Cohort admin")
    expect(first).to_be_visible()
    first_top = first.evaluate("el => el.getBoundingClientRect().top")
    second_top = second.evaluate("el => el.getBoundingClientRect().top")
    assert second_top - first_top >= 24
