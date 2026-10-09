"""Browser flows for the notification bell and the notification centre.

The Django test client covers what the server renders: badge counts, panel and
list contents, filtering, paging, isolation and the focus markers it emits.
What only a browser shows is covered here: the Alpine bell opening and closing
by mouse and keyboard, the HTMX swaps, where keyboard focus really lands, the
URL and history behaviour, and the panel's layout on a phone.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Locator, Page, expect

from django.urls import reverse

from freedom_ls.accounts.models import User
from freedom_ls.comms.factories import NotificationFactory
from freedom_ls.comms.models import Notification
from freedom_ls.conftest import reverse_url
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

PHONE_WIDTH = 375


def _bell(page: Page) -> Locator:
    # By id, not accessible name: once the panel has loaded, its close
    # button's name ("Close notifications") also contains "Notifications",
    # so a name-based lookup stops being unique.
    return page.locator("#notification-bell")


def _bell_label(page: Page) -> Locator:
    return page.locator("#notification-bell-label")


def _requests_to(page: Page, url_name: str) -> list[str]:
    """Every request the page issues to the named URL from now on."""
    path = reverse(url_name)
    seen: list[str] = []

    def record(request) -> None:
        if path in request.url:
            seen.append(request.url)

    page.on("request", record)
    return seen


def _centre_url(live_server) -> str:
    return reverse_url(live_server, "comms:notification_list")


def _row(page: Page, title: str) -> Locator:
    return page.locator("#notification-list li", has_text=title)


def _unread_marker(row: Locator) -> Locator:
    return row.get_by_text("Unread", exact=True)


def _focused_id(page: Page) -> str:
    return str(page.evaluate("document.activeElement.id"))


def test_notifications_flow(
    live_server,
    logged_in_page: Page,
    logged_in_user: User,
    mock_site_context,
    settings,
) -> None:
    settings.NOTIFICATION_BADGE_POLL_SECONDS = 1
    page = logged_in_page
    bell = _bell(page)
    panel_heading = page.get_by_role("heading", name="Notifications")
    NotificationFactory(user=logged_in_user, target__title="Registered Course")
    NotificationFactory(user=logged_in_user, target__title="Other Course")

    # The bell shows the badge; Enter on the focused bell opens the panel.
    page.goto(reverse_url(live_server, "learner_interface:dashboard"))
    expect(_bell_label(page)).to_have_text("Notifications, 2 new")
    panel_requests = _requests_to(page, "comms:notification_panel")
    bell.focus()
    page.keyboard.press("Enter")
    expect(bell).to_have_attribute("aria-expanded", "true")
    expect(panel_heading).to_be_visible()
    expect(
        page.get_by_text("You've been registered for Registered Course")
    ).to_be_visible()

    # Opening zeroes the badge with one request.
    expect(_bell_label(page)).to_have_text("Notifications, none new")
    assert len(panel_requests) == 1

    # Escape closes the panel and returns focus to the bell.
    page.keyboard.press("Escape")
    expect(bell).to_have_attribute("aria-expanded", "false")
    assert _focused_id(page) == "notification-bell"

    # Mark all as read, from the keyboard, updates the panel and badge with one
    # request and moves focus to the panel heading.
    bell.click()
    expect(bell).to_have_attribute("aria-expanded", "true")
    mark_all = page.get_by_role("button", name="Mark all as read")
    expect(mark_all).to_be_enabled()
    mark_all_requests = _requests_to(page, "comms:notification_mark_all_read")
    mark_all.focus()
    page.keyboard.press("Enter")
    expect(mark_all).to_be_disabled()
    expect(page.locator("#notification-panel-heading")).to_be_focused()
    expect(
        page.locator("#notification-panel ul").get_by_text("Unread", exact=True)
    ).to_have_count(0)
    expect(_bell_label(page)).to_have_text("Notifications, none new")
    assert len(mark_all_requests) == 1
    page.keyboard.press("Escape")
    expect(bell).to_have_attribute("aria-expanded", "false")

    # A new notification refreshes the badge on the poll and keeps focus on the bell.
    bell.focus()
    NotificationFactory(user=logged_in_user, target__title="Gamma Course")
    expect(_bell_label(page)).to_have_text("Notifications, 1 new", timeout=5000)
    assert _focused_id(page) == "notification-bell"

    # The centre: the unread filter lists only unread rows.
    NotificationFactory(user=logged_in_user, target__title="Newest Course")
    page.goto(_centre_url(live_server))
    page.get_by_role("navigation", name="Filter").get_by_role(
        "link", name="Unread"
    ).click()
    expect(page).to_have_url(re.compile(r"[?&]filter=unread\b"))
    expect(_row(page, "Gamma Course")).to_be_visible()
    expect(page.get_by_text("Registered Course")).to_have_count(0)

    # Marking a row read in the unread view removes it and moves focus to the
    # next row's button.
    _row(page, "Newest Course").get_by_role("button", name="Mark read").focus()
    page.keyboard.press("Enter")
    expect(page.get_by_text("Newest Course")).to_have_count(0)
    expect(
        _row(page, "Gamma Course").get_by_role("button", name="Mark read")
    ).to_be_focused()

    # Back in the full list, a row toggles read then unread.
    page.get_by_role("navigation", name="Filter").get_by_role(
        "link", name="All", exact=True
    ).click()
    expect(_row(page, "Newest Course")).to_be_visible()
    gamma_unread = _unread_marker(_row(page, "Gamma Course"))
    expect(gamma_unread).to_be_visible()
    _row(page, "Gamma Course").get_by_role("button", name="Mark read").click()
    expect(page).to_have_url(re.compile(r"/notifications/?$"))
    expect(gamma_unread).to_have_count(0)
    _row(page, "Gamma Course").get_by_role("button", name="Mark unread").click()
    expect(gamma_unread).to_be_visible()

    # Clicking a row outside the message text opens its target.
    gamma = Notification.objects.get(data__course_title="Gamma Course")
    _row(page, "Gamma Course").click(position={"x": 12, "y": 12})
    expect(page).to_have_url(re.compile(re.escape(live_server.url + gamma.url)))

    # Mark all as read clears every marker and moves keyboard focus to the banner.
    NotificationFactory.create_batch(2, user=logged_in_user)
    page.goto(_centre_url(live_server))
    expect(
        page.locator("#notification-list ul").get_by_text("Unread", exact=True).first
    ).to_be_visible()
    page.get_by_role("button", name="Mark all as read").focus()
    page.keyboard.press("Enter")
    banner = page.get_by_text("You're up to date. Everything has been read.")
    expect(banner).to_be_focused()
    expect(
        page.locator("#notification-list ul").get_by_text("Unread", exact=True)
    ).to_have_count(0)

    # Pagination pushes the page into the URL and survives a reload.
    NotificationFactory.create_batch(19, user=logged_in_user)
    page.goto(_centre_url(live_server))
    expect(page.locator("#notification-list li")).to_have_count(20)
    page.get_by_role("link", name="2", exact=True).click()
    expect(page).to_have_url(re.compile(r"[?&]page=2\b"))
    expect(page.locator("#notification-list li")).to_have_count(5)
    page.reload()
    expect(page.locator("#notification-list li")).to_have_count(5)
    expect(page.get_by_text("Registered Course")).to_be_visible()

    # The unread filter survives a reload and Back restores the full list.
    page.get_by_role("navigation", name="Filter").get_by_role(
        "link", name="Unread"
    ).click()
    expect(page).to_have_url(re.compile(r"[?&]filter=unread\b"))
    page.reload()
    expect(page.get_by_text("Registered Course")).to_have_count(0)
    page.go_back()
    expect(page).to_have_url(re.compile(r"[?&]page=2\b"))
    expect(page.get_by_text("Registered Course")).to_be_visible()
    # The whole page came back, not just the list fragment.
    expect(page.get_by_role("heading", name="Notifications", level=1)).to_be_visible()

    # Layout: the open panel is a full-width sheet on a phone.
    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(reverse_url(live_server, "learner_interface:dashboard"))
        bell.click()
        panel = page.locator("#notification-panel")
        expect(panel).to_be_visible()
        assert_no_horizontal_overflow(page)
        if viewport["width"] == PHONE_WIDTH:
            box = panel.bounding_box()
            assert box is not None
            assert box["width"] == pytest.approx(PHONE_WIDTH, abs=1)
            expect(
                page.get_by_role("button", name="Close notifications")
            ).to_be_visible()


def test_a_failed_reopen_shows_the_error_and_try_again_recovers(
    live_server, logged_in_page: Page, logged_in_user: User, mock_site_context
) -> None:
    NotificationFactory(user=logged_in_user, target__title="First Course")
    page = logged_in_page
    page.goto(reverse_url(live_server, "learner_interface:dashboard"))
    bell = _bell(page)
    list_ = page.locator("#notification-panel ul")
    bell.click()
    expect(list_).to_be_visible()
    bell.click()
    panel_url = f"**{reverse('comms:notification_panel')}*"
    page.route(panel_url, lambda route: route.fulfill(status=500))

    bell.click()

    error = page.get_by_role("alert").filter(
        has_text="Couldn't load your notifications"
    )
    expect(error).to_be_visible()
    expect(list_).to_be_hidden()

    page.unroute(panel_url)
    page.get_by_role("button", name="Try again").click()

    expect(list_).to_be_visible()
    expect(error).to_be_hidden()
