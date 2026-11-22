"""Browser flow for direct messaging: inbox, thread and back on a phone.

The Django test client covers what the server renders. What only a browser
shows is covered here: following a row into a thread, the back link returning
to the inbox with the row no longer unread, and the layout at each viewport.
"""

from __future__ import annotations

import re
from typing import cast

import pytest
from playwright.sync_api import Page, Route, expect
from pytest_django.fixtures import SettingsWrapper
from pytest_django.live_server_helper import LiveServer

from django.contrib.sites.models import Site
from django.db.models import QuerySet

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.comms.factories import ConversationFactory, MessageFactory
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

    def can_start(
        self, *, sender: User, recipient: User, site: Site
    ) -> MessagingDecision:
        return MessagingDecision.allow()

    def can_reply(
        self, *, sender: User, recipient: User, site: Site, conversation: Conversation
    ) -> MessagingDecision:
        return MessagingDecision.allow()

    def recipients_for(self, *, sender: User, site: Site) -> QuerySet[User]:
        return User.objects.filter(site=site).exclude(pk=sender.pk)


class ClosedPolicy(OpenPolicy):
    """Refuses every reply."""

    def can_reply(
        self, *, sender: User, recipient: User, site: Site, conversation: Conversation
    ) -> MessagingDecision:
        return MessagingDecision.refuse(MessagingRefusal.CLOSED_BY_CONFIGURATION)


def test_inbox_to_thread_and_back_on_a_phone(
    live_server: LiveServer,
    logged_in_page: Page,
    logged_in_user: User,
    mock_site_context: Site,
    settings: SettingsWrapper,
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

    # The thread pane is hidden while the list shows, and browser back from
    # a thread returns to the list.
    expect(page.get_by_text("Select a conversation to read it.")).to_be_hidden()
    page.get_by_role("link", name="Kai Ngata").click()
    expect(page.get_by_text("Welcome to the course")).to_be_visible()
    expect(page.get_by_role("link", name="Kai Ngata")).to_have_count(0)
    page.go_back()
    expect(page.get_by_role("heading", name="Messages")).to_be_visible()
    expect(page.get_by_role("link", name="Kai Ngata")).to_be_visible()

    # A link inside the viewer's own bubble is not painted in the bubble's colour.
    own = MessageFactory(
        conversation=Conversation.objects.get(),
        sender=logged_in_user,
        body="See https://example.com/a for details",
    )
    page.goto(
        reverse_url(live_server, "conversations:thread", args=[own.conversation.pk])
    )
    own_link = page.locator("li[data-own] a[href='https://example.com/a']")
    expect(own_link).to_be_visible()
    link_colour, bubble_colour = own_link.evaluate(
        "el => [getComputedStyle(el).color,"
        " getComputedStyle(el.parentElement).backgroundColor]"
    )
    assert link_colour != bubble_colour

    # Layout: no horizontal overflow on the inbox or the thread at any viewport.
    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(reverse_url(live_server, "conversations:inbox"))
        assert_no_horizontal_overflow(page)
        page.get_by_role("link", name="Kai Ngata").first.click()
        expect(page.get_by_text("Welcome to the course")).to_be_visible()
        assert_no_horizontal_overflow(page)


def test_picker_search_choose_and_send_on_a_phone(
    live_server: LiveServer,
    logged_in_page: Page,
    logged_in_user: User,
    mock_site_context: Site,
    settings: SettingsWrapper,
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


def test_messages_page_new_message_flow(
    live_server: LiveServer,
    logged_in_page: Page,
    logged_in_user: User,
    mock_site_context: Site,
    settings: SettingsWrapper,
) -> None:
    """On the messages page at desktop width: the New message link swaps the
    picker into the thread pane without a reload, a send leaves /messages/new,
    and a thread picked from the pane picker fits the viewport."""
    settings.MESSAGING_ENABLED = True
    settings.MESSAGING_POLICY = f"{__name__}.OpenPolicy"
    page = logged_in_page
    page.set_viewport_size({"width": 1280, "height": 800})
    UserFactory(first_name="Kai", last_name="Ngata")

    page.goto(reverse_url(live_server, "conversations:inbox"))
    # A marker that survives only while the document is not reloaded.
    page.evaluate("window.sameDocument = true")

    page.get_by_label("Conversations").get_by_role("link", name="New message").and_(
        page.locator(":visible")
    ).click()
    expect(page.locator("#thread-pane #recipient-picker")).to_be_visible()
    assert page.evaluate("window.sameDocument === true"), (
        "New message link reloaded the document"
    )

    page.get_by_role("link", name="Kai Ngata").click()
    page.get_by_label("Message to Kai Ngata").fill("Hello Kai")
    page.get_by_role("button", name="Send").click()

    expect(page.get_by_text("Hello Kai")).to_be_visible()
    assert "/messages/new" not in page.url, "send left the user on /messages/new"

    # Picking someone in the pane picker swaps the thread in without the page
    # setup a full load gives it, which once left the document one header
    # taller than the viewport and pushed the composer below the fold.
    viewport = {"width": 1920, "height": 1080}
    page.set_viewport_size(viewport)
    page.goto(reverse_url(live_server, "conversations:inbox"))
    page.get_by_label("Conversations").get_by_role("link", name="New message").and_(
        page.locator(":visible")
    ).click()
    expect(page.locator("#thread-pane #recipient-picker")).to_be_visible()
    page.locator("#recipient-results").get_by_role("link", name="Kai Ngata").click()

    send = page.get_by_role("button", name="Send")
    expect(send).to_be_visible()
    expect(page, "pane picker did not land on the thread URL").to_have_url(
        re.compile(r"/messages/[0-9a-f-]{36}/$")
    )
    send_bottom = send.evaluate("el => el.getBoundingClientRect().bottom")
    scroll_height = page.evaluate("document.documentElement.scrollHeight")
    assert send_bottom <= viewport["height"], (
        "Send below the fold after the pane picker"
    )
    assert scroll_height <= viewport["height"], (
        "document taller than the viewport after the pane picker"
    )


def test_thread_receives_a_polled_message_and_keeps_the_typed_draft(
    live_server: LiveServer,
    logged_in_page: Page,
    logged_in_user: User,
    mock_site_context: Site,
    settings: SettingsWrapper,
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


def _open_thread(
    live_server: LiveServer, page: Page, user: User, settings: SettingsWrapper
) -> Conversation:
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
        .order_by("created_at")
        .values_list("body", flat=True)
    )


def test_thread_composer_flow(
    live_server: LiveServer,
    logged_in_page: Page,
    logged_in_user: User,
    mock_site_context: Site,
    settings: SettingsWrapper,
) -> None:
    """The composer on a thread page: a double click posts once and returns
    focus to the box, Send is disabled while a request is in flight, Ctrl+Enter
    sends, the character counter shows only near the limit, a network failure
    offers a Retry that sends once with the same client key, and a refused send
    keeps the draft and shows the reason."""
    page = logged_in_page
    conversation = _open_thread(live_server, page, logged_in_user, settings)
    box = page.get_by_label("Message to Kai Ngata")
    send = page.get_by_role("button", name="Send")
    sent: list[str] = []

    # A double click on Send posts once and focus returns to the box.
    box.fill("Only once")
    send.dblclick()
    expect(page.get_by_text("Only once")).to_have_count(1)
    expect(box, "focus did not return to the box after sending").to_be_focused()
    sent.append("Only once")
    assert _sent_bodies(conversation) == sent, "double click did not post exactly once"

    # The Send button stays disabled for the whole request. It used to stay
    # enabled because the form, not the button, issues the request.
    def delay_then_continue(route: Route) -> None:
        page.wait_for_timeout(1500)
        route.continue_()

    page.route("**/messages/*/send/", delay_then_continue)
    box.fill("Slow send")
    send.click()
    expect(send, "Send enabled while the request was in flight").to_be_disabled()
    expect(page.get_by_text("Slow send")).to_have_count(1)
    expect(send).to_be_enabled()
    page.unroute("**/messages/*/send/", delay_then_continue)
    sent.append("Slow send")
    assert _sent_bodies(conversation) == sent, "slow send did not post exactly once"

    # Ctrl+Enter sends, and the hint says so.
    expect(page.get_by_text("Ctrl+Enter to send")).to_be_visible()
    box.fill("From the keyboard")
    box.press("Control+Enter")
    expect(page.get_by_text("From the keyboard")).to_be_visible()
    sent.append("From the keyboard")
    assert _sent_bodies(conversation) == sent, "Ctrl+Enter did not send the message"

    # The counter is hidden at 1799 characters and shows 150 left at 1850.
    counter = page.locator("#composer [aria-live=polite]")
    box.fill("a" * 1799)
    expect(counter, "counter shown at 1799 characters").to_be_hidden()
    box.fill("a" * 1850)
    expect(counter).to_have_text("150 characters left")
    box.fill("")

    # A network failure offers Retry, which sends once with the same key.
    key = page.locator("#composer input[name=client_key]").input_value()
    page.route("**/messages/*/send/", lambda route: route.abort())
    box.fill("Flaky network")
    send.click()
    alert = page.get_by_role("alert").filter(has_text="Not sent. Check your connection")
    expect(alert).to_be_visible()
    assert _sent_bodies(conversation) == sent, "aborted request still stored a message"

    page.unroute("**/messages/*/send/")
    alert.get_by_role("button", name="Retry").click()
    expect(page.get_by_text("Flaky network")).to_have_count(1)
    expect(alert).to_be_hidden()
    sent.append("Flaky network")
    assert _sent_bodies(conversation) == sent, "Retry did not send exactly once"
    assert page.locator("#composer input[name=client_key]").input_value() != key, (
        "client key was not rotated after the retry"
    )

    # A refused send keeps the draft and shows the reason. Last, because it
    # switches the policy to one that refuses every reply.
    settings.MESSAGING_POLICY = f"{__name__}.ClosedPolicy"
    box.fill("Still my draft")
    send.click()
    expect(page.locator("#composer").get_by_role("alert")).to_be_visible()
    expect(box, "refused send cleared the draft").to_have_value("Still my draft")
    assert _sent_bodies(conversation) == sent, "refused send stored a message"


OFFSET_IN_LOG = (
    "el => el.getBoundingClientRect().top"
    " - document.querySelector('#thread-log').getBoundingClientRect().top"
)


COMPOSER_VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1280, "height": 800},
    {"width": 768, "height": 1024},
    PHONE,
]


def test_long_thread_flow(
    live_server: LiveServer,
    logged_in_page: Page,
    logged_in_user: User,
    mock_site_context: Site,
    settings: SettingsWrapper,
) -> None:
    """A 65-message thread: loading earlier messages from the top keeps the
    reader's place, loading the final page removes the control without shifting
    the view, and the composer stays inside the viewport at every width."""
    settings.MESSAGING_ENABLED = True
    settings.MESSAGING_POLICY = f"{__name__}.OpenPolicy"
    page = logged_in_page
    page.set_viewport_size({"width": 1280, "height": 800})
    kai = UserFactory(first_name="Kai", last_name="Ngata")
    conversation = ConversationFactory(between=(logged_in_user, kai))
    for number in range(1, 66):
        MessageFactory(
            conversation=conversation, sender=kai, body=f"Entry {number:02d}"
        )
    thread_url = reverse_url(
        live_server, "conversations:thread", kwargs={"pk": conversation.pk}
    )
    page.goto(thread_url)
    log = page.locator("#thread-log")
    load_earlier = page.get_by_role("button", name="Load earlier messages")
    reading = page.get_by_text("Entry 36", exact=True)
    expect(reading).to_be_visible()

    # Prepending older messages with the log scrolled to the top used to leave
    # scrollTop at 0, jumping the reader to the oldest message. The log scrolls
    # by the height of the prepended entries, so the entry the reader was
    # looking at has not moved.
    log.evaluate("el => { el.scrollTop = 0; }")
    top_before = reading.evaluate(OFFSET_IN_LOG)
    load_earlier.click()
    expect(page.get_by_text("Entry 06", exact=True)).to_be_attached()
    page.wait_for_function("() => document.querySelector('#thread-log').scrollTop > 0")
    top_after = reading.evaluate(OFFSET_IN_LOG)
    assert abs(top_after - top_before) < 2, (
        "first load-earlier moved the entry the reader was looking at"
    )

    # Loading the final page removed the control above the log, which grew the
    # log and moved the entry the reader was looking at upward.
    reading = page.get_by_text("Entry 06", exact=True)
    log.evaluate("el => { el.scrollTop = 0; }")
    top_before = reading.evaluate("el => el.getBoundingClientRect().top")
    load_earlier.click()
    expect(page.get_by_text("Entry 01", exact=True)).to_be_attached()
    expect(load_earlier, "load-earlier control left after the last page").to_have_count(
        0
    )
    page.wait_for_function("() => document.querySelector('#thread-log').scrollTop > 0")
    top_after = reading.evaluate("el => el.getBoundingClientRect().top")
    assert abs(top_after - top_before) < 2, "final load-earlier page shifted the view"

    # The site footer and page spacing were once stacked on top of a
    # viewport-tall pane, so the document scrolled and pushed the composer
    # below the fold.
    for viewport in COMPOSER_VIEWPORTS:
        width = viewport["width"]
        page.set_viewport_size(viewport)
        page.goto(thread_url)
        expect(page.get_by_text("Entry 65", exact=True)).to_be_visible()
        send = page.get_by_role("button", name="Send")
        expect(send, f"Send not visible at {width}px").to_be_visible()
        hint_bottom = page.get_by_text("Ctrl+Enter").first.evaluate(
            "el => el.getBoundingClientRect().bottom"
        )
        send_bottom = send.evaluate("el => el.getBoundingClientRect().bottom")
        scroll_height = page.evaluate("document.documentElement.scrollHeight")
        assert max(hint_bottom, send_bottom) <= viewport["height"], (
            f"composer below the fold at {width}px"
        )
        assert scroll_height <= viewport["height"], (
            f"document taller than the viewport at {width}px"
        )
