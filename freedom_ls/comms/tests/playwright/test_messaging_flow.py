"""Browser flow for direct messaging: inbox, thread and back on a phone.

The Django test client covers what the server renders. What only a browser
shows is covered here: following a row into a thread, the back link returning
to the inbox with the row no longer unread, and the layout at each viewport.
"""

from __future__ import annotations

from typing import cast

import pytest
from playwright.sync_api import Page, expect

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.comms.factories import ConversationFactory, MessageFactory
from freedom_ls.comms.messaging_loader import get_messaging_policy
from freedom_ls.comms.messaging_policy import (
    MessagingDecision,
    MessagingPolicy,
    MessagingRefusal,
)
from freedom_ls.comms.models import Conversation, Message
from freedom_ls.conftest import reverse_url
from freedom_ls.tests.playwright_helpers import (
    QA_VIEWPORTS,
    assert_no_horizontal_overflow,
)

# transaction=True so the live server's own DB connection sees the fixture
# data this test's connection committed.
pytestmark = [pytest.mark.playwright, pytest.mark.django_db(transaction=True)]

PHONE = {"width": 375, "height": 812}


class OpenPolicy(MessagingPolicy):
    """Lets everyone on the site message everyone else."""

    def can_start(self, *, sender, recipient, site):
        return MessagingDecision.allow()

    def can_reply(self, *, sender, recipient, site, conversation):
        return MessagingDecision.allow()

    def recipients_for(self, *, sender, site):
        return User.objects.filter(site=site).exclude(pk=sender.pk)


class ClosedPolicy(OpenPolicy):
    """Refuses every reply."""

    def can_reply(self, *, sender, recipient, site, conversation):
        return MessagingDecision.refuse(MessagingRefusal.CLOSED_BY_CONFIGURATION)


def test_inbox_to_thread_and_back_on_a_phone(
    live_server,
    logged_in_page: Page,
    logged_in_user: User,
    mock_site_context,
    settings,
) -> None:
    settings.MESSAGING_ENABLED = True
    page = logged_in_page
    page.set_viewport_size(PHONE)
    kai = UserFactory(first_name="Kai", last_name="Ngata")
    MessageFactory(
        conversation=ConversationFactory(between=(logged_in_user, kai)),
        sender=kai,
        body="Welcome to the course",
    )

    # The inbox lists the conversation as unread.
    page.goto(reverse_url(live_server, "conversations:inbox"))
    row = page.get_by_role("link", name="Kai Ngata")
    expect(row).to_be_visible()
    expect(row.get_by_text("Unread", exact=True)).to_be_visible()

    # Opening it shows the message and a back link; the list pane is hidden.
    row.click()
    expect(page.get_by_text("Welcome to the course")).to_be_visible()
    back = page.get_by_role("link", name="Back to messages")
    expect(back).to_be_visible()

    # Back returns to the inbox, where the row is now read.
    back.click()
    expect(page.get_by_role("heading", name="Messages")).to_be_visible()
    expect(
        page.get_by_role("link", name="Kai Ngata").get_by_text("Unread", exact=True)
    ).to_have_count(0)

    # Layout: no horizontal overflow on the inbox or the thread at any viewport.
    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(reverse_url(live_server, "conversations:inbox"))
        assert_no_horizontal_overflow(page)
        page.get_by_role("link", name="Kai Ngata").first.click()
        expect(page.get_by_text("Welcome to the course")).to_be_visible()
        assert_no_horizontal_overflow(page)


def test_picker_search_choose_and_send_on_a_phone(
    live_server,
    logged_in_page: Page,
    logged_in_user: User,
    mock_site_context,
    settings,
) -> None:
    settings.MESSAGING_ENABLED = True
    settings.MESSAGING_POLICY = f"{__name__}.OpenPolicy"
    page = logged_in_page
    page.set_viewport_size(PHONE)
    UserFactory(first_name="Kai", last_name="Ngata")
    UserFactory(first_name="Ana", last_name="Smith")

    page.goto(reverse_url(live_server, "conversations:start"))
    expect(page.get_by_role("heading", name="New message")).to_be_visible()

    # Typing narrows the list to the matching person.
    page.get_by_label("To").fill("kai")
    expect(page.get_by_role("link", name="Kai Ngata")).to_be_visible()
    expect(page.get_by_role("link", name="Ana Smith")).to_have_count(0)

    # Choosing a person shows the composer addressed to them.
    page.get_by_role("link", name="Kai Ngata").click()
    expect(page.get_by_label("Message to Kai Ngata")).to_be_visible()

    # Sending lands in the new thread.
    page.get_by_label("Message to Kai Ngata").fill("Hello Kai")
    page.get_by_role("button", name="Send").click()
    expect(page.get_by_text("Hello Kai")).to_be_visible()

    # Layout: the picker has no horizontal overflow at any viewport.
    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(reverse_url(live_server, "conversations:start"))
        assert_no_horizontal_overflow(page)


def test_thread_receives_a_polled_message_and_keeps_the_typed_draft(
    live_server,
    logged_in_page: Page,
    logged_in_user: User,
    mock_site_context,
    settings,
) -> None:
    settings.MESSAGING_ENABLED = True
    settings.MESSAGING_POLICY = f"{__name__}.OpenPolicy"
    settings.MESSAGE_THREAD_POLL_SECONDS = 1
    page = logged_in_page
    kai = UserFactory(first_name="Kai", last_name="Ngata")
    conversation = ConversationFactory(between=(logged_in_user, kai))
    MessageFactory(conversation=conversation, sender=kai, body="Welcome to the course")
    page.goto(
        reverse_url(live_server, "conversations:thread", kwargs={"pk": conversation.pk})
    )
    box = page.get_by_label("Message to Kai Ngata")
    expect(page.get_by_text("Welcome to the course")).to_be_visible()

    # A message arrives while a reply is half typed.
    box.fill("Half a reply")
    MessageFactory(
        conversation=conversation, sender=kai, body="Did you see the new topic?"
    )

    # The poll appends it and leaves the draft alone.
    expect(page.get_by_text("Did you see the new topic?")).to_be_visible()
    expect(box).to_have_value("Half a reply")

    # The announcement names the sender and the count, never the text.
    status = page.locator("#thread-status")
    expect(status).to_have_text("1 new message from Kai Ngata")
    assert "Did you see" not in (status.text_content() or "")

    # Layout: no horizontal overflow at any viewport.
    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        assert_no_horizontal_overflow(page)


def _open_thread(live_server, page: Page, user: User, settings) -> Conversation:
    settings.MESSAGING_ENABLED = True
    settings.MESSAGING_POLICY = f"{__name__}.OpenPolicy"
    kai = UserFactory(first_name="Kai", last_name="Ngata")
    conversation = cast("Conversation", ConversationFactory(between=(user, kai)))
    MessageFactory(conversation=conversation, sender=kai, body="Welcome to the course")
    page.goto(
        reverse_url(live_server, "conversations:thread", kwargs={"pk": conversation.pk})
    )
    expect(page.get_by_text("Welcome to the course")).to_be_visible()
    return conversation


def _sent_bodies(conversation: Conversation) -> list[str]:
    return list(
        Message.objects.filter(conversation=conversation)
        .exclude(body="Welcome to the course")
        .values_list("body", flat=True)
    )


def test_a_double_click_on_send_posts_once_and_focus_returns_to_the_box(
    live_server,
    logged_in_page: Page,
    logged_in_user: User,
    mock_site_context,
    settings,
) -> None:
    page = logged_in_page
    conversation = _open_thread(live_server, page, logged_in_user, settings)

    box = page.get_by_label("Message to Kai Ngata")
    box.fill("Only once")
    page.get_by_role("button", name="Send").dblclick()

    expect(page.get_by_text("Only once")).to_have_count(1)
    expect(box).to_be_focused()
    assert _sent_bodies(conversation) == ["Only once"]


def test_ctrl_enter_sends_the_message(
    live_server,
    logged_in_page: Page,
    logged_in_user: User,
    mock_site_context,
    settings,
) -> None:
    page = logged_in_page
    conversation = _open_thread(live_server, page, logged_in_user, settings)

    expect(page.get_by_text("Ctrl+Enter to send")).to_be_visible()
    box = page.get_by_label("Message to Kai Ngata")
    box.fill("From the keyboard")
    box.press("Control+Enter")

    expect(page.get_by_text("From the keyboard")).to_be_visible()
    assert _sent_bodies(conversation) == ["From the keyboard"]


def test_a_refused_send_keeps_the_draft_and_shows_the_reason(
    live_server,
    logged_in_page: Page,
    logged_in_user: User,
    mock_site_context,
    settings,
) -> None:
    page = logged_in_page
    conversation = _open_thread(live_server, page, logged_in_user, settings)
    settings.MESSAGING_POLICY = f"{__name__}.ClosedPolicy"
    get_messaging_policy.cache_clear()

    box = page.get_by_label("Message to Kai Ngata")
    box.fill("Still my draft")
    page.get_by_role("button", name="Send").click()

    expect(page.locator("#composer").get_by_role("alert")).to_be_visible()
    expect(page.get_by_label("Message to Kai Ngata")).to_have_value("Still my draft")
    assert _sent_bodies(conversation) == []


def test_the_counter_appears_near_the_limit(
    live_server,
    logged_in_page: Page,
    logged_in_user: User,
    mock_site_context,
    settings,
) -> None:
    page = logged_in_page
    _open_thread(live_server, page, logged_in_user, settings)

    box = page.get_by_label("Message to Kai Ngata")
    box.fill("a" * 1799)
    counter = page.locator("#composer [aria-live=polite]")
    expect(counter).to_be_hidden()
    box.fill("a" * 1850)
    expect(counter).to_have_text("150 characters left")


def test_a_network_failure_offers_retry_that_sends_once_with_the_same_key(
    live_server,
    logged_in_page: Page,
    logged_in_user: User,
    mock_site_context,
    settings,
) -> None:
    page = logged_in_page
    conversation = _open_thread(live_server, page, logged_in_user, settings)
    key = page.locator("#composer input[name=client_key]").input_value()

    page.route("**/messages/*/send/", lambda route: route.abort())
    box = page.get_by_label("Message to Kai Ngata")
    box.fill("Flaky network")
    page.get_by_role("button", name="Send").click()

    alert = page.get_by_role("alert").filter(has_text="Not sent. Check your connection")
    expect(alert).to_be_visible()
    assert _sent_bodies(conversation) == []

    page.unroute("**/messages/*/send/")
    alert.get_by_role("button", name="Retry").click()

    expect(page.get_by_text("Flaky network")).to_have_count(1)
    expect(alert).to_be_hidden()
    assert _sent_bodies(conversation) == ["Flaky network"]
    assert page.locator("#composer input[name=client_key]").input_value() != key


OFFSET_IN_LOG = (
    "el => el.getBoundingClientRect().top"
    " - document.querySelector('#thread-log').getBoundingClientRect().top"
)


def test_loading_earlier_messages_from_the_top_keeps_the_readers_place(
    live_server,
    logged_in_page: Page,
    logged_in_user: User,
    mock_site_context,
    settings,
) -> None:
    """Prepending older messages with the log scrolled to the top used to
    leave scrollTop at 0, jumping the reader to the oldest message."""
    settings.MESSAGING_ENABLED = True
    settings.MESSAGING_POLICY = f"{__name__}.OpenPolicy"
    page = logged_in_page
    kai = UserFactory(first_name="Kai", last_name="Ngata")
    conversation = ConversationFactory(between=(logged_in_user, kai))
    for number in range(1, 36):
        MessageFactory(
            conversation=conversation, sender=kai, body=f"Entry {number:02d}"
        )
    page.goto(
        reverse_url(live_server, "conversations:thread", kwargs={"pk": conversation.pk})
    )
    log = page.locator("#thread-log")
    reading = page.get_by_text("Entry 06", exact=True)
    expect(reading).to_be_visible()

    # The reader sits at the top of the log, looking at the oldest loaded entry.
    log.evaluate("el => { el.scrollTop = 0; }")
    top_before = reading.evaluate(OFFSET_IN_LOG)

    page.get_by_role("button", name="Load earlier messages").click()
    expect(page.get_by_text("Entry 01", exact=True)).to_be_attached()

    # The log scrolled by the height of the prepended entries, so the entry
    # the reader was looking at has not moved.
    page.wait_for_function("() => document.querySelector('#thread-log').scrollTop > 0")
    top_after = reading.evaluate(OFFSET_IN_LOG)
    assert abs(top_after - top_before) < 2
