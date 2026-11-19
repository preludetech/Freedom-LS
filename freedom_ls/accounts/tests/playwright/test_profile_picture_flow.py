"""Browser flow for the account area: the Personal details page and its sidebar.

The Django test client covers what the server renders. What only a browser
shows is covered here: the name saving inline with its toast, the sidebar
leading to allauth's pages, and the layout at each viewport.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from freedom_ls.accounts.models import User
from freedom_ls.conftest import reverse_url
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def test_change_the_name_inline_then_follow_the_sidebar(
    live_server, logged_in_page: Page, logged_in_user: User
) -> None:
    page = logged_in_page
    page.goto(reverse_url(live_server, "accounts:account_profile"))

    expect(page).to_have_url(
        reverse_url(
            live_server,
            "accounts:account_profile",
            kwargs={"path_string": "personal-details"},
        )
    )

    page.get_by_label("First name").fill("Ada")
    page.get_by_label("Last name").fill("Lovelace")
    page.get_by_role("button", name="Save", exact=True).click()

    expect(page.get_by_text("Name saved")).to_be_visible()
    expect(page.get_by_label("First name")).to_have_value("Ada")
    expect(page.get_by_label("Last name")).to_have_value("Lovelace")
    stored = User._base_manager.get(pk=logged_in_user.pk)
    assert (stored.first_name, stored.last_name) == ("Ada", "Lovelace")

    page.get_by_role("navigation", name="Account").get_by_role(
        "link", name="Email"
    ).click()

    expect(page).to_have_url(reverse_url(live_server, "account_email"))

    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(page)
