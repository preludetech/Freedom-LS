"""Browser-only behaviour of the notification centre: HTMX-driven filter
switching, marking a row read/unread, marking all as read, and paginating.
None of these swaps happens under the Django test client, which never
executes the hx-get/hx-post request a real browser fires on click.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from django.urls import reverse

from freedom_ls.accounts.models import User
from freedom_ls.comms.factories import NotificationFactory

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]


def _centre_url(live_server) -> str:
    return f"{live_server.url}{reverse('comms:notification_list')}"


def test_the_unread_filter_shows_only_unread_rows(
    live_server, logged_in_page: Page, logged_in_user: User, mock_site_context
) -> None:
    NotificationFactory(user=logged_in_user, target__title="Alpha Course")
    seen = NotificationFactory(user=logged_in_user, target__title="Beta Course")
    seen.read_at = seen.created_at
    seen.save(update_fields=["read_at"])

    page = logged_in_page
    page.goto(_centre_url(live_server))

    page.get_by_role("navigation", name="Filter").get_by_role(
        "link", name="Unread"
    ).click()

    expect(page.get_by_text("Alpha Course")).to_be_visible()
    expect(page.get_by_text("Beta Course")).to_have_count(0)


def test_marking_a_row_read_then_unread_toggles_its_unread_marker(
    live_server, logged_in_page: Page, logged_in_user: User, mock_site_context
) -> None:
    NotificationFactory(user=logged_in_user, target__title="Toggle Course")

    page = logged_in_page
    page.goto(_centre_url(live_server))

    row = page.locator("li", has_text="Toggle Course")
    expect(row.get_by_text("Unread", exact=True)).to_be_visible()

    row.get_by_role("button", name="Mark read").click()
    expect(
        page.locator("li", has_text="Toggle Course").get_by_text("Unread", exact=True)
    ).to_have_count(0)

    page.locator("li", has_text="Toggle Course").get_by_role(
        "button", name="Mark unread"
    ).click()
    expect(
        page.locator("li", has_text="Toggle Course").get_by_text("Unread", exact=True)
    ).to_be_visible()


def test_mark_all_as_read_clears_every_unread_marker(
    live_server, logged_in_page: Page, logged_in_user: User, mock_site_context
) -> None:
    NotificationFactory(user=logged_in_user, target__title="First Course")
    NotificationFactory(user=logged_in_user, target__title="Second Course")

    page = logged_in_page
    page.goto(_centre_url(live_server))

    page.get_by_role("button", name="Mark all as read").click()

    expect(
        page.get_by_text("You're up to date. Everything has been read.")
    ).to_be_visible()
    # Scoped to the rows themselves: the toolbar's own "Unread" filter link
    # text is untouched by marking every row read.
    expect(
        page.locator("#notification-list ul").get_by_text("Unread", exact=True)
    ).to_have_count(0)


def test_pagination_loads_the_second_page(
    live_server, logged_in_page: Page, logged_in_user: User, mock_site_context
) -> None:
    NotificationFactory.create_batch(25, user=logged_in_user)

    page = logged_in_page
    page.goto(_centre_url(live_server))

    expect(page.locator("#notification-list li")).to_have_count(20)

    page.get_by_role("link", name="2", exact=True).click()

    expect(page.locator("#notification-list li")).to_have_count(5)
