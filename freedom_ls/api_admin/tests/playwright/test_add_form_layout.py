"""The API key add form in the admin at phone and tablet widths."""

from __future__ import annotations

import pytest
from allauth.account.models import EmailAddress
from playwright.sync_api import Page
from pytest_django.live_server_helper import LiveServer

from django.contrib.sites.models import Site
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.tests.playwright_fixtures import sign_in
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


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


def test_api_key_add_form_flow(
    live_server: LiveServer, page: Page, admin_user: User
) -> None:
    """The add form fits every viewport, shows scope labels in full and wraps the issued key.

    Long scope labels used to not wrap, so the form scrolled sideways, and they were cut
    off with an ellipsis, hiding the models they cover. A key with no dashes ran past its
    box on a phone, clipping its middle. The issued-key step runs last because it submits
    the form.
    """
    sign_in(page, live_server, admin_user)
    add_url = f"{live_server.url}{reverse('admin:freedom_ls_api_apikey_add')}"

    for viewport in QA_VIEWPORTS:
        width = viewport["width"]
        page.set_viewport_size(viewport)
        page.goto(add_url)
        assert_no_horizontal_overflow(page)
        label_texts = page.locator("input[name=scopes] + span")
        assert label_texts.count() > 0, f"no scope labels at {width}px"
        clipped = label_texts.evaluate_all(
            "els => els.filter(e => e.scrollWidth > e.clientWidth)"
            ".map(e => e.textContent)"
        )
        assert clipped == [], f"scope labels clipped at {width}px: {clipped}"

    page.set_viewport_size(QA_VIEWPORTS[0])
    page.goto(add_url)
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
    assert fits, "issued key runs past its box on a phone"
    assert_no_horizontal_overflow(page)
