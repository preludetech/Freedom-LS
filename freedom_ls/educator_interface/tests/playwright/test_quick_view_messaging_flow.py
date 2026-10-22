"""Browser flow for messaging a learner from the educator quick view.

The Django test client covers what the server renders. What only a browser
shows is covered here: the drawer staying open through a send, the Open
conversation link appearing after the first message, the discard prompt for an
unsent draft, and the bottom sheet on a phone.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
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


def _learners_url(live_server, organisation_slug: str) -> str:
    path = reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation_slug, "path_string": "learners"},
    )
    return f"{live_server.url}{path}"


def _thread_href(organisation_slug: str) -> re.Pattern[str]:
    """A pattern matching a thread address inside the organisation."""
    return re.compile(rf"/{re.escape(organisation_slug)}/messages/[0-9a-f-]{{36}}$")


def test_messaging_a_learner_from_the_quick_view(
    live_server,
    educator_logged_in_page: Page,
    educator_user: User,
    mock_site_context,
    settings,
) -> None:
    settings.MESSAGING_ENABLED = True
    settings.MESSAGING_POLICY = f"{__name__}.OpenPolicy"
    page = educator_logged_in_page
    page.set_viewport_size(QA_VIEWPORTS[2])
    organisation = OrganisationFactory()
    grantor = LearnerFactory(user__superuser=True).user
    assign_role(grantor, educator_user, "organisation_admin", organisation)
    for first, last in (("Kai", "Ngata"), ("Mere", "Tane")):
        LearnerFactory(
            organisation=organisation,
            user=UserFactory(first_name=first, last_name=last),
        )
    quick_view = page.locator("#quick-view")
    box = quick_view.get_by_label("Message to Kai Ngata")
    prompt = page.locator("[data-quick-view-discard-prompt]")
    open_link = quick_view.get_by_role("link", name="Open conversation")

    page.goto(_learners_url(live_server, organisation.slug))
    page.get_by_role("link", name="Quick view: Kai Ngata", exact=True).first.click()
    expect(quick_view).to_be_visible()
    expect(quick_view.locator("#quick-view-title")).to_have_text("Kai Ngata")

    # No conversation yet, so no Open conversation link.
    expect(open_link).to_be_hidden()

    # The first send keeps the drawer open, shows the entry, and reveals the
    # link to the new conversation.
    box.fill("Welcome to the course")
    quick_view.get_by_role("button", name="Send").click()
    expect(quick_view.locator("#quick-view-message-box")).to_contain_text(
        "Welcome to the course"
    )
    expect(quick_view).to_be_visible()
    expect(box).to_have_value("")
    expect(open_link).to_be_visible()
    expect(open_link).to_have_attribute("href", _thread_href(organisation.slug))

    # The fresh composer after a send is not a draft: another learner opens
    # without a prompt.
    page.get_by_role("link", name="Quick view: Mere Tane", exact=True).first.click()
    expect(quick_view.locator("#quick-view-title")).to_have_text("Mere Tane")
    expect(prompt).to_be_hidden()

    # An unsent draft asks before the next learner opens.
    page.get_by_label("Message to Mere Tane").fill("Half a thought")
    page.get_by_role("link", name="Quick view: Kai Ngata", exact=True).first.click()
    expect(prompt).to_be_visible()
    prompt.get_by_role("button", name="Keep editing").click()
    expect(prompt).to_be_hidden()
    expect(page.get_by_label("Message to Mere Tane")).to_have_value("Half a thought")

    page.get_by_role("link", name="Quick view: Kai Ngata", exact=True).first.click()
    prompt.get_by_role("button", name="Discard").click()
    expect(quick_view.locator("#quick-view-title")).to_have_text("Kai Ngata")
    expect(prompt).to_be_hidden()
    expect(quick_view.get_by_text("Welcome to the course")).to_be_visible()

    # Discarding a draft while closing the drawer drops it: reopening the same
    # learner shows an empty box.
    box.fill("Closing draft")
    page.keyboard.press("Escape")
    expect(prompt).to_be_visible()
    prompt.get_by_role("button", name="Discard").click()
    expect(quick_view).to_be_hidden()
    page.get_by_role("link", name="Quick view: Kai Ngata", exact=True).first.click()
    expect(quick_view).to_be_visible()
    expect(box).to_have_value("")


def test_sending_from_the_quick_view_bottom_sheet_on_a_phone(
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
        user=UserFactory(first_name="Kai", last_name="Ngata"),
    )
    quick_view = page.locator("#quick-view")

    page.goto(_learners_url(live_server, organisation.slug))
    page.get_by_role("link", name="Quick view: Kai Ngata", exact=True).first.click()
    expect(quick_view).to_be_visible()
    expect(quick_view).to_have_css("transform", "none")
    sheet = quick_view.bounding_box()
    assert sheet is not None
    assert sheet["x"] == 0
    assert sheet["width"] == PHONE["width"]
    assert sheet["y"] + sheet["height"] == PHONE["height"]

    quick_view.get_by_label("Message to Kai Ngata").fill("On my way")
    quick_view.get_by_role("button", name="Send").click()
    expect(quick_view.locator("#quick-view-message-box")).to_contain_text("On my way")
    expect(quick_view).to_be_visible()
    assert_no_horizontal_overflow(page)

    # Layout: the drawer holding the box has no horizontal overflow at any viewport.
    for viewport in QA_VIEWPORTS:
        page.set_viewport_size(viewport)
        page.goto(_learners_url(live_server, organisation.slug))
        page.get_by_role("link", name="Quick view: Kai Ngata", exact=True).first.click()
        expect(quick_view.get_by_label("Message to Kai Ngata")).to_be_visible()
        assert_no_horizontal_overflow(page)
