"""Browser flow for direct messaging: inbox, thread and back on a phone.

The Django test client covers what the server renders. What only a browser
shows is covered here: following a row into a thread, the back link returning
to the inbox with the row no longer unread, and the layout at each viewport.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.comms.factories import ConversationFactory, MessageFactory
from freedom_ls.comms.messaging_policy import MessagingDecision, MessagingPolicy
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
