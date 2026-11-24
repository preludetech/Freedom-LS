"""The course progress admin changelist on a phone.

Below the ``lg`` breakpoint unfold turns each changelist row into a card whose
cells are flex boxes and whose field label is a ``::before`` pseudo-element. The
rule that lets long values wrap anywhere is inherited by that label, which then
shrinks to one character and breaks mid-word ("Learn" / "er"). Computed style
of a pseudo-element is only available in a real browser.
"""

from __future__ import annotations

import pytest
from allauth.account.models import EmailAddress
from playwright.sync_api import Page, expect
from pytest_django.live_server_helper import LiveServer

from django.contrib.sites.models import Site
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.learner_management.factories import (
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.tests.playwright_fixtures import sign_in

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_PHONE_VIEWPORT = {"width": 375, "height": 812}

_LABEL_OVERFLOW_WRAP_JS = """
() => Array.from(document.querySelectorAll("#result_list td[data-label]"))
    .map((cell) => getComputedStyle(cell, "::before").overflowWrap)
"""

_VALUE_OVERFLOW_WRAP_JS = """
() => Array.from(document.querySelectorAll("#result_list td"))
    .map((cell) => getComputedStyle(cell).overflowWrap)
"""


@pytest.fixture
def admin_user(db: None, live_server_site: Site, mock_site_context: Site) -> User:
    """A fresh, email-verified superuser."""
    user: User = UserFactory(superuser=True)
    EmailAddress.objects.get_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )
    return user


def test_changelist_card_labels_do_not_break_mid_word(
    live_server: LiveServer, page: Page, admin_user: User
) -> None:
    """A card's field label used to break mid-word; values still wrap anywhere."""
    page.set_viewport_size(_PHONE_VIEWPORT)
    sign_in(page, live_server, admin_user)
    # With transaction=True the on_commit signal receivers run, so registering
    # the learner creates the CourseProgress row the changelist lists.
    LearnerCourseRegistrationFactory(
        learner=LearnerFactory(
            user=UserFactory(email="a.rather.long.learner.address@example.com")
        )
    )

    page.goto(
        f"{live_server.url}"
        f"{reverse('admin:freedom_ls_learner_progress_courseprogress_changelist')}"
    )

    expect(page.locator("#result_list td[data-label]").first).to_be_visible()
    label_wraps = page.evaluate(_LABEL_OVERFLOW_WRAP_JS)
    assert label_wraps
    assert set(label_wraps) == {"normal"}
    assert "anywhere" in page.evaluate(_VALUE_OVERFLOW_WRAP_JS)
