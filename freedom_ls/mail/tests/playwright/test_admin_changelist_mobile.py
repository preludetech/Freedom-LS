"""The outbound email admin changelist on a phone.

Below the ``lg`` breakpoint unfold turns each changelist row into a card whose
cells are fixed at 45px with ``overflow: hidden``, so a long subject or last
error is cut off. Whether a cell clips is a layout fact only a real browser can
settle.
"""

from __future__ import annotations

import pytest
from allauth.account.models import EmailAddress
from playwright.sync_api import Page, expect
from pytest_django.live_server_helper import LiveServer

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.sites.models import Site
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.mail.factories import OutboundEmailFactory
from freedom_ls.tests.playwright_fixtures import sign_in

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_CLIPPED_CELLS_JS = """
() => Array.from(document.querySelectorAll("#result_list td, #result_list th"))
    .filter((cell) => cell.scrollHeight > cell.clientHeight)
    .map((cell) => cell.textContent.trim())
"""


@pytest.fixture
def admin_user(
    db: None, live_server_site: Site, mock_site_context: Site
) -> AbstractBaseUser:
    """A fresh, email-verified superuser."""
    user: AbstractBaseUser = UserFactory(superuser=True)
    EmailAddress.objects.get_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )
    return user


def test_changelist_card_cells_grow_to_fit_a_long_last_error(
    live_server: LiveServer, page: Page, admin_user: AbstractBaseUser
) -> None:
    OutboundEmailFactory(
        failed=True,
        subject="A subject long enough to wrap onto a second line on a phone",
        recipients=["a.rather.long.recipient.address@example.test"],
        last_error="smtplib.SMTPServerDisconnected: " + "connection dropped " * 10,
    )
    page.set_viewport_size({"width": 375, "height": 812})
    sign_in(page, live_server, admin_user)

    page.goto(
        f"{live_server.url}{reverse('admin:freedom_ls_mail_outboundemail_changelist')}"
    )

    expect(
        page.get_by_text("smtplib.SMTPServerDisconnected", exact=False)
    ).to_be_visible()
    assert page.evaluate(_CLIPPED_CELLS_JS) == []
