"""Browser flow for the educator Messages section on a phone.

The Django test client covers what the server renders. What only a browser
shows is covered here: following a card into the thread, sending a reply, the
back control returning to the list, and the layout at each viewport.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.comms.factories import ConversationFactory, MessageFactory
from freedom_ls.comms.messaging_policy import MessagingDecision, MessagingPolicy
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
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


def _section_url(live_server, organisation_slug: str, path_string: str) -> str:
    path = reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation_slug, "path_string": path_string},
    )
    return f"{live_server.url}{path}"


def test_list_to_thread_reply_and_back_on_a_phone(
    live_server,
    educator_logged_in_page: Page,
    educator_user: User,
    mock_site_context,
    settings,
) -> None:
    settings.MESSAGING_ENABLED = True
    settings.MESSAGING_POLICY = f"{__name__}.OpenPolicy"
    page = educator_logged_in_page
    page.set_viewport_size(PHONE)
    organisation = OrganisationFactory()
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    kai = LearnerFactory(
        organisation=organisation,
        user=UserFactory(first_name="Kai", last_name="Ngata"),
    ).user
    conversation = ConversationFactory(between=(educator_user, kai))
    MessageFactory(
        conversation=conversation,
        sender=kai,
        body="Could you look at supercalifragilisticexpialidocious_" + "x" * 60,
    )

    # The list shows the conversation as unread.
    page.goto(_section_url(live_server, organisation.slug, "messages"))
    card = page.get_by_role("link", name="Kai Ngata").locator("visible=true")
    expect(card).to_be_visible()
    unread = page.get_by_text("Unread", exact=True).locator("visible=true")
    expect(unread).to_be_visible()
    assert_no_horizontal_overflow(page)

    # Opening it shows the thread, with the back control before the name.
    card.click()
    back = page.get_by_role("link", name="Back to messages")
    expect(back).to_be_visible()
    expect(page.get_by_role("heading", name="Kai Ngata", level=2)).to_be_visible()
    expect(page.get_by_text("Could you look at")).to_be_visible()
    assert_no_horizontal_overflow(page)

    # The composer stays in view and Send is an icon with the name "Send".
    box = page.get_by_label("Message to Kai Ngata")
    send = page.get_by_role("button", name="Send")
    expect(box).to_be_in_viewport()
    expect(send).to_be_in_viewport()
    expect(send).to_have_text("", use_inner_text=True)

    # Sending a reply appends it to the log.
    box.fill("On it, thanks")
    send.click()
    expect(page.locator("#thread-log").get_by_text("On it, thanks")).to_be_visible()

    # Back returns to the list, where the conversation is no longer unread.
    back.click()
    expect(
        page.get_by_role("link", name="Kai Ngata").locator("visible=true")
    ).to_be_visible()
    expect(
        page.get_by_text("Unread", exact=True).locator("visible=true")
    ).to_have_count(0)

    # Layout: the list and the thread have no horizontal overflow at any viewport.
    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(_section_url(live_server, organisation.slug, "messages"))
        assert_no_horizontal_overflow(page)
        page.goto(
            _section_url(live_server, organisation.slug, f"messages/{conversation.pk}")
        )
        expect(page.get_by_text("On it, thanks")).to_be_visible()
        assert_no_horizontal_overflow(page)


def test_new_message_from_the_top_bar_on_a_phone(
    live_server,
    educator_logged_in_page: Page,
    educator_user: User,
    mock_site_context,
    settings,
) -> None:
    settings.MESSAGING_ENABLED = True
    settings.MESSAGING_POLICY = f"{__name__}.OpenPolicy"
    page = educator_logged_in_page
    page.set_viewport_size(PHONE)
    organisation = OrganisationFactory()
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    LearnerFactory(
        organisation=organisation,
        user=UserFactory(
            first_name="Kai", last_name="Ngata", email="kai.ngata@example.com"
        ),
    )

    # New message is reachable from the list and opens the modal as a bottom sheet.
    page.goto(_section_url(live_server, organisation.slug, "messages"))
    page.get_by_role("button", name="New message").locator("visible=true").click()
    dialog = page.get_by_role("dialog", name="New message")
    expect(dialog).to_be_visible()
    box = dialog.bounding_box()
    assert box is not None
    assert box["x"] == 0
    assert box["width"] == PHONE["width"]
    assert_no_horizontal_overflow(page)

    # Searching lists the matching learner with the email, in a row tall enough to tap.
    dialog.get_by_label("To").fill("Ka")
    row = dialog.get_by_role("link", name="Kai Ngata")
    expect(row).to_be_visible()
    expect(row).to_contain_text("kai.ngata@example.com")
    row_box = row.bounding_box()
    assert row_box is not None
    assert row_box["height"] >= 24
    assert_no_horizontal_overflow(page)

    # Choosing the learner shows the composer; sending lands on the thread.
    row.click()
    expect(dialog.get_by_text("To Kai Ngata", exact=True)).to_be_visible()
    dialog.get_by_label("Message to Kai Ngata").fill("Welcome to the course")
    dialog.get_by_role("button", name="Send").click()
    expect(page.get_by_role("link", name="Back to messages")).to_be_visible()
    expect(
        page.locator("#thread-log").get_by_text("Welcome to the course")
    ).to_be_visible()
    expect(dialog).to_be_hidden()

    # Layout: the modal has no horizontal overflow at any viewport.
    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(_section_url(live_server, organisation.slug, "messages"))
        page.get_by_role("button", name="New message").locator("visible=true").click()
        expect(page.get_by_role("dialog", name="New message")).to_be_visible()
        assert_no_horizontal_overflow(page)
