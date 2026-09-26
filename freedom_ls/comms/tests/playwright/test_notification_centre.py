"""Browser-only behaviour of the notification centre: HTMX-driven filter
switching, marking a row read/unread, marking all as read, and paginating.
None of these swaps happens under the Django test client, which never
executes the hx-get/hx-post request a real browser fires on click.
"""

from __future__ import annotations

import re
from datetime import timedelta

import pytest
from playwright.sync_api import Page, expect

from django.urls import reverse

from freedom_ls.accounts.models import User
from freedom_ls.comms.factories import NotificationFactory
from freedom_ls.comms.models import Notification

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


def test_paginating_pushes_the_page_into_the_url(
    live_server, logged_in_page: Page, logged_in_user: User, mock_site_context
) -> None:
    NotificationFactory.create_batch(25, user=logged_in_user)

    page = logged_in_page
    page.goto(_centre_url(live_server))

    page.get_by_role("link", name="2", exact=True).click()

    expect(page).to_have_url(re.compile(r"[?&]page=2\b"))
    page.reload()
    expect(page.locator("#notification-list li")).to_have_count(5)


def test_the_unread_filter_survives_reload_and_back_restores_all(
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

    expect(page).to_have_url(re.compile(r"[?&]filter=unread\b"))
    page.reload()
    expect(page.get_by_text("Beta Course")).to_have_count(0)

    page.go_back()

    expect(page).to_have_url(_centre_url(live_server))
    expect(page.get_by_text("Beta Course")).to_be_visible()
    # The whole page came back, not just the list fragment.
    expect(page.get_by_role("heading", name="Notifications", level=1)).to_be_visible()


def test_keyboard_mark_all_as_read_moves_focus_to_the_up_to_date_banner(
    live_server, logged_in_page: Page, logged_in_user: User, mock_site_context
) -> None:
    NotificationFactory.create_batch(2, user=logged_in_user)

    page = logged_in_page
    page.goto(_centre_url(live_server))
    page.get_by_role("button", name="Mark all as read").focus()
    page.keyboard.press("Enter")

    expect(
        page.get_by_text("You're up to date. Everything has been read.")
    ).to_be_focused()


def test_mark_read_in_the_unread_view_moves_focus_to_the_next_rows_button(
    live_server, logged_in_page: Page, logged_in_user: User, mock_site_context
) -> None:
    older = NotificationFactory(user=logged_in_user, target__title="Older Course")
    newer = NotificationFactory(user=logged_in_user, target__title="Newer Course")
    Notification._base_manager.filter(pk=older.pk).update(
        created_at=newer.created_at - timedelta(minutes=1)
    )

    page = logged_in_page
    page.goto(f"{_centre_url(live_server)}?filter=unread")
    page.locator("li", has_text="Newer Course").get_by_role(
        "button", name="Mark read"
    ).focus()
    page.keyboard.press("Enter")

    expect(page.get_by_text("Newer Course")).to_have_count(0)
    expect(
        page.locator("li", has_text="Older Course").get_by_role(
            "button", name="Mark read"
        )
    ).to_be_focused()
