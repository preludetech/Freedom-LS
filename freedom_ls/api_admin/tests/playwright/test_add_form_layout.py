"""The API key add form in the admin at phone and tablet widths."""

from __future__ import annotations

import pytest
from allauth.account.models import EmailAddress
from playwright.sync_api import Page

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.tests.playwright_fixtures import _LOGGED_IN_PASSWORD, _login_via_ui
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


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


def test_add_form_fits_the_viewport_with_long_scope_labels(
    live_server, page: Page, admin_user: User
) -> None:
    """The long scope labels did not wrap, so the add form scrolled sideways."""
    _login_via_ui(page, live_server, str(admin_user.email), _LOGGED_IN_PASSWORD)

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(f"{live_server.url}{reverse('admin:freedom_ls_api_apikey_add')}")
        assert_no_horizontal_overflow(page)


def test_issued_key_wraps_inside_its_box_on_a_phone(
    live_server, page: Page, admin_user: User
) -> None:
    """A key with no dashes ran past its box on a phone, clipping its middle."""
    _login_via_ui(page, live_server, str(admin_user.email), _LOGGED_IN_PASSWORD)
    page.set_viewport_size(QA_VIEWPORTS[0])
    page.goto(f"{live_server.url}{reverse('admin:freedom_ls_api_apikey_add')}")
    page.fill("input[name=name]", "Phone key")
    page.locator("input[name=scopes]").first.check()
    page.get_by_role("button", name="Save", exact=False).first.click()

    key_box = page.locator("code.select-all")
    key_box.wait_for()
    # A real secret may contain a dash, which is a wrap point; this one has none.
    key_box.evaluate(
        "el => { el.textContent = 'flsk_' + 'a'.repeat(16) + '.' + 'b'.repeat(43); }"
    )

    fits = key_box.evaluate("el => el.scrollWidth <= el.clientWidth")
    assert fits
    assert_no_horizontal_overflow(page)


def test_scope_labels_show_their_full_text_at_every_viewport(
    live_server, page: Page, admin_user: User
) -> None:
    """Scope labels were cut off with an ellipsis, hiding the models they cover."""
    _login_via_ui(page, live_server, str(admin_user.email), _LOGGED_IN_PASSWORD)

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(f"{live_server.url}{reverse('admin:freedom_ls_api_apikey_add')}")
        label_texts = page.locator("input[name=scopes] + span")
        assert label_texts.count() > 0
        clipped = label_texts.evaluate_all(
            "els => els.filter(e => e.scrollWidth > e.clientWidth)"
            ".map(e => e.textContent)"
        )
        assert clipped == [], f"clipped at {viewport}"
        assert_no_horizontal_overflow(page)
