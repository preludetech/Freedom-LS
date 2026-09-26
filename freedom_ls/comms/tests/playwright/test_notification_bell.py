"""Browser-only behaviour of the bell panel: opening and closing it by mouse
and keyboard, the badge zeroing in the same response, marking all as read
from the panel, the live poll picking up a new notification, a real
self-registration showing up, and the mobile full-width sheet. None of this
is observable under the Django test client, which never runs the Alpine
component or executes the hx-get a real browser fires on click.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from django.urls import reverse

from freedom_ls.accounts.models import User
from freedom_ls.comms.factories import NotificationFactory
from freedom_ls.conftest import reverse_url

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

_MOBILE_VIEWPORT = {"width": 375, "height": 812}


def _bell(page: Page):
    # By id, not accessible name: once the panel has loaded, its close
    # button's name ("Close notifications") also contains "Notifications",
    # so a name-based lookup stops being unique.
    return page.locator("#notification-bell")


def _bell_label(page: Page):
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


def test_click_opens_the_panel_and_sets_aria_expanded(
    live_server, logged_in_page: Page, logged_in_user: User, mock_site_context
) -> None:
    page = logged_in_page
    page.goto(reverse_url(live_server, "learner_interface:dashboard"))
    bell = _bell(page)

    bell.click()

    expect(bell).to_have_attribute("aria-expanded", "true")
    expect(page.get_by_role("heading", name="Notifications")).to_be_visible()


def test_escape_closes_the_panel_and_returns_focus_to_the_bell(
    live_server, logged_in_page: Page, logged_in_user: User, mock_site_context
) -> None:
    page = logged_in_page
    page.goto(reverse_url(live_server, "learner_interface:dashboard"))
    bell = _bell(page)
    bell.click()
    expect(bell).to_have_attribute("aria-expanded", "true")

    page.keyboard.press("Escape")

    expect(bell).to_have_attribute("aria-expanded", "false")
    assert page.evaluate("document.activeElement.id") == "notification-bell"


def test_keyboard_enter_on_the_focused_bell_opens_the_panel(
    live_server, logged_in_page: Page, logged_in_user: User, mock_site_context
) -> None:
    page = logged_in_page
    page.goto(reverse_url(live_server, "learner_interface:dashboard"))
    bell = _bell(page)
    bell.focus()

    page.keyboard.press("Enter")

    expect(bell).to_have_attribute("aria-expanded", "true")


def test_opening_the_panel_zeroes_the_badge_with_one_request(
    live_server, logged_in_page: Page, logged_in_user: User, mock_site_context
) -> None:
    NotificationFactory.create_batch(2, user=logged_in_user)
    page = logged_in_page
    page.goto(reverse_url(live_server, "learner_interface:dashboard"))
    expect(_bell_label(page)).to_have_text("Notifications, 2 new")
    panel_requests = _requests_to(page, "comms:notification_panel")

    _bell(page).click()

    expect(_bell_label(page)).to_have_text("Notifications, none new")
    assert len(panel_requests) == 1


def test_mark_all_as_read_updates_the_panel_and_badge_with_one_request(
    live_server, logged_in_page: Page, logged_in_user: User, mock_site_context
) -> None:
    NotificationFactory(user=logged_in_user, target__title="First Course")
    NotificationFactory(user=logged_in_user, target__title="Second Course")
    page = logged_in_page
    page.goto(reverse_url(live_server, "learner_interface:dashboard"))
    _bell(page).click()
    expect(page.get_by_role("heading", name="Notifications")).to_be_visible()
    mark_all_requests = _requests_to(page, "comms:notification_mark_all_read")

    page.get_by_role("button", name="Mark all as read").click()

    expect(
        page.locator("#notification-panel ul").get_by_text("Unread", exact=True)
    ).to_have_count(0)
    expect(_bell_label(page)).to_have_text("Notifications, none new")
    assert len(mark_all_requests) == 1


def test_keyboard_mark_all_as_read_moves_focus_to_the_panel_heading(
    live_server, logged_in_page: Page, logged_in_user: User, mock_site_context
) -> None:
    NotificationFactory.create_batch(2, user=logged_in_user)
    page = logged_in_page
    page.goto(reverse_url(live_server, "learner_interface:dashboard"))
    _bell(page).click()
    mark_all = page.get_by_role("button", name="Mark all as read")
    expect(mark_all).to_be_enabled()

    mark_all.focus()
    page.keyboard.press("Enter")

    expect(mark_all).to_be_disabled()
    expect(page.locator("#notification-panel-heading")).to_be_focused()


def test_badge_refresh_picks_up_a_new_notification_and_keeps_focus_on_the_bell(
    live_server, logged_in_page: Page, logged_in_user: User, mock_site_context, settings
) -> None:
    settings.NOTIFICATION_BADGE_POLL_SECONDS = 1
    page = logged_in_page
    page.goto(reverse_url(live_server, "learner_interface:dashboard"))
    _bell(page).focus()

    NotificationFactory(user=logged_in_user)

    expect(_bell_label(page)).to_have_text("Notifications, 1 new", timeout=3000)
    assert page.evaluate("document.activeElement.id") == "notification-bell"


def test_self_registering_shows_the_registration_notification_in_the_panel(
    live_server,
    logged_in_page: Page,
    logged_in_user: User,
    mock_site_context,
    course_with_topic,
) -> None:
    course = course_with_topic(access_type="free", title="Playwright Fundamentals")
    page = logged_in_page

    page.goto(
        reverse_url(
            live_server,
            "learner_interface:course_detail",
            kwargs={"course_slug": course.slug},
        )
    )
    page.get_by_role("link", name="Enrol for free").click()
    _bell(page).click()

    expect(
        page.get_by_text("You're registered for Playwright Fundamentals")
    ).to_be_visible()


def test_the_open_panel_is_a_full_width_sheet_at_375px(
    live_server, logged_in_page: Page, logged_in_user: User, mock_site_context
) -> None:
    page = logged_in_page
    page.set_viewport_size(_MOBILE_VIEWPORT)
    page.goto(reverse_url(live_server, "learner_interface:dashboard"))

    _bell(page).click()

    panel = page.locator("#notification-panel")
    expect(panel).to_be_visible()
    box = panel.bounding_box()
    assert box is not None
    assert box["width"] == pytest.approx(_MOBILE_VIEWPORT["width"], abs=1)
    expect(page.get_by_role("button", name="Close notifications")).to_be_visible()


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
