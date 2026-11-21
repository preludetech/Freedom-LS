"""The learner page's Messages tab: educator_interface/panels/learner/messages.py.

The educator's own conversation, the composer that posts back into the tab, and the
oversight dialog that opens a colleague's conversation read-only.
"""

from __future__ import annotations

import json
from typing import cast
from uuid import uuid4

import lxml.html
import pytest

from django.test import Client

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.audit_log.writer import subject_key
from freedom_ls.comms.factories import MessageFactory
from freedom_ls.comms.messaging import (
    SendResult,
    encode_cursor,
    inbox_for,
    unread_conversation_count,
)
from freedom_ls.comms.messaging_policy import MessagingRefusal
from freedom_ls.comms.models import Conversation
from freedom_ls.educator_interface.messaging import OwnConversation
from freedom_ls.educator_interface.tests.helpers import (
    _get_document,
    _grant,
    _learner_page,
    _msg_conversation,
    _msg_educator,
    _msg_learner,
    _older_url,
    _open_conversation,
    _oversight_scene,
    _tab_url,
    _view_conversation_url,
    _viewed_entries,
    messages_section,
)
from freedom_ls.learner_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
)
from freedom_ls.learner_management.models import Learner
from freedom_ls.organisations.factories import OrganisationFactory

# The learner page's Messages tab: the educator's own conversation with the
# learner, and the composer that posts back into the tab.


def _send_url(learner: Learner) -> str:
    return f"{_tab_url(learner)}/__panels/conversation/__actions/send"


def _tab_document(client: Client, learner: Learner) -> lxml.html.HtmlElement:
    return _get_document(client, _tab_url(learner))


@pytest.mark.django_db
@messages_section
class TestLearnerMessagesTab:
    def test_the_tab_is_in_the_learner_pages_tab_row(self, msg_client_for):
        organisation = OrganisationFactory()
        educator = _msg_educator(organisation)
        learner = _msg_learner(organisation)

        document = _learner_page(msg_client_for(educator), learner)

        assert document.xpath(f"//a[@href='{_tab_url(learner)}']")

    def test_the_tab_is_absent_and_its_url_404s_when_messaging_is_off(
        self, msg_client_for, settings
    ):
        settings.MESSAGING_ENABLED = False
        organisation = OrganisationFactory()
        educator = _msg_educator(organisation)
        learner = _msg_learner(organisation)
        client = msg_client_for(educator)

        document = _learner_page(client, learner)

        assert not document.xpath(f"//a[@href='{_tab_url(learner)}']")
        assert client.get(_tab_url(learner)).status_code == 404

    def test_it_shows_the_educators_own_conversation_and_not_a_colleagues(
        self, msg_client_for
    ):
        organisation = OrganisationFactory()
        educator = _msg_educator(organisation)
        colleague = _msg_educator(organisation)
        learner = _msg_learner(organisation)
        own = _msg_conversation(educator, learner.user)
        MessageFactory(conversation=own, sender=learner.user, body="for me")
        theirs = _msg_conversation(colleague, learner.user)
        MessageFactory(conversation=theirs, sender=learner.user, body="for them")

        document = _tab_document(msg_client_for(educator), learner)

        for section in document.xpath("//section[@data-panel='others']"):
            section.getparent().remove(section)
        text = document.text_content()
        assert "for me" in text
        assert "for them" not in text

    def test_the_thread_inside_the_panel_draws_no_header_of_its_own(
        self, msg_client_for
    ):
        """The panel's Messages title heads the conversation, so the thread
        adds no second header (avatar, name and a rule under them), and it
        keeps the card's padding and rounded corners."""
        organisation = OrganisationFactory()
        educator = _msg_educator(organisation)
        learner = _msg_learner(organisation)
        conversation = _msg_conversation(educator, learner.user)
        MessageFactory(conversation=conversation, sender=learner.user, body="hi")

        document = _tab_document(msg_client_for(educator), learner)

        (panel,) = document.xpath("//section[@data-panel='conversation']")
        (pane,) = panel.xpath(".//section[@x-data='conversationThread']")
        assert not pane.xpath(".//header")
        assert not pane.xpath(".//h1 | .//h2 | .//h3")
        classes = pane.get("class").split()
        assert "rounded-b-lg" in classes
        assert "sm:[&_[data-inset]]:px-6" in classes
        assert "[&_#composer]:border-t-0" in classes

    def test_a_learner_with_no_conversation_shows_a_prompt_and_a_composer_posting_to_the_tab(
        self, msg_client_for
    ):
        organisation = OrganisationFactory()
        educator = _msg_educator(organisation)
        learner = _msg_learner(organisation)

        document = _tab_document(msg_client_for(educator), learner)

        assert "No messages with Ada Lovelace yet." in document.text_content()
        composer = document.xpath("//form[@id='composer']")[0]
        assert composer.get("hx-post") == _send_url(learner)
        region_id = document.xpath("//section[@data-panel='conversation']")[0].get("id")
        assert composer.get("hx-target") == f"#{region_id}"
        assert composer.get("hx-swap") == "outerHTML"

    def test_the_composer_before_a_first_message_sits_on_the_panels_padding_with_no_rule(
        self, msg_client_for
    ):
        """The composer used to draw a rule above itself and sit 8px left of
        the panel's heading, on its own 16px padding instead of the panel's."""
        organisation = OrganisationFactory()
        educator = _msg_educator(organisation)
        learner = _msg_learner(organisation)

        document = _tab_document(msg_client_for(educator), learner)

        (composer,) = document.xpath("//form[@id='composer']")
        classes = composer.get("class").split()
        assert "border-t" not in classes
        assert "px-4" not in classes
        wrapper = composer.getparent()
        assert {"px-4", "sm:px-6"} <= set(wrapper.get("class").split())

    def test_opening_the_tab_moves_the_educators_read_marker(self, msg_client_for):
        organisation = OrganisationFactory()
        educator = _msg_educator(organisation)
        learner = _msg_learner(organisation)
        conversation = _msg_conversation(educator, learner.user)
        MessageFactory(conversation=conversation, sender=learner.user, body="hi")
        assert unread_conversation_count(educator) == 1

        _tab_document(msg_client_for(educator), learner)

        assert unread_conversation_count(educator) == 0

    def test_an_educator_of_another_organisation_gets_404(self, msg_client_for):
        organisation = OrganisationFactory()
        learner = _msg_learner(organisation)
        outsider = _msg_educator(OrganisationFactory())

        response = msg_client_for(outsider).get(_tab_url(learner))

        assert response.status_code == 404

    def test_an_organisation_admin_sees_the_learners_educator_conversations_but_not_peers_or_their_own(
        self, msg_client_for
    ):
        organisation = OrganisationFactory()
        admin = _msg_educator(organisation)
        colleague = _msg_educator(organisation)
        peer = _msg_learner(organisation, first_name="Peer", last_name="Person")
        learner = _msg_learner(organisation)
        own = _msg_conversation(admin, learner.user)
        MessageFactory(conversation=own, sender=admin, body="my own words")
        theirs = _msg_conversation(colleague, learner.user)
        MessageFactory(conversation=theirs, sender=colleague, body="colleague words")
        among_peers = _msg_conversation(peer.user, learner.user)
        MessageFactory(conversation=among_peers, sender=peer.user, body="peer words")

        document = _tab_document(msg_client_for(admin), learner)

        (section,) = document.xpath("//section[@data-panel='others']")
        text = section.text_content()
        assert "Other educator conversations" in text
        assert colleague.display_name in text
        assert "colleague words" in text
        assert "my own words" not in text
        assert "peer words" not in text
        assert "Peer Person" not in text

    def test_the_conversation_row_is_a_small_person_row_in_one_button(
        self, msg_client_for
    ):
        """The other educator is a small semibold name beside a small avatar.
        It used to render at the base size and regular weight beside a medium
        avatar."""
        organisation = OrganisationFactory()
        admin = _msg_educator(organisation)
        colleague = _msg_educator(organisation)
        learner = _msg_learner(organisation)
        theirs = _msg_conversation(colleague, learner.user)
        MessageFactory(conversation=theirs, sender=colleague, body="colleague words")

        document = _tab_document(msg_client_for(admin), learner)

        (section,) = document.xpath("//section[@data-panel='others']")
        (button,) = section.cssselect("li button")
        (name,) = [
            n
            for n in button.cssselect("span.truncate")
            if n.text_content().strip() == colleague.display_name
        ]
        classes = " ".join(
            " ".join(
                a.get("class", "")
                for a in [name, *name.iterancestors("span", "div")]
                if a.getparent() is not None and a.tag != "li"
            ).split()
        )
        assert "text-sm" in classes
        assert "font-semibold" in classes
        assert button.cssselect("span.size-6")
        assert not button.cssselect("span.size-8")
        assert "colleague words" in button.text_content()

    def test_a_site_admin_sees_the_list(self, msg_client_for, mock_site_context):
        organisation = OrganisationFactory()
        site_admin = cast(User, UserFactory(staff=True))
        _grant(site_admin, "site_admin", mock_site_context)
        colleague = _msg_educator(organisation)
        learner = _msg_learner(organisation)
        _msg_conversation(colleague, learner.user)

        document = _tab_document(msg_client_for(site_admin), learner)

        assert colleague.display_name in document.text_content()
        assert document.xpath("//section[@data-panel='others']//h2")

    @pytest.mark.parametrize("role", ["cohort_admin", "cohort_viewer"])
    def test_a_cohort_role_sees_no_list(self, msg_client_for, role):
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)
        learner = _msg_learner(organisation)
        CohortMembershipFactory(cohort=cohort, learner=learner)
        educator = cast(User, UserFactory(staff=True))
        _grant(educator, role, cohort)
        colleague = _msg_educator(organisation)
        _msg_conversation(colleague, learner.user)

        document = _tab_document(msg_client_for(educator), learner)

        assert "Other educator conversations" not in document.text_content()
        assert not document.xpath("//*[@id='oversight-heading']")

    def test_a_deactivated_learner_shows_the_empty_state(self, msg_client_for):
        organisation = OrganisationFactory()
        admin = _msg_educator(organisation)
        learner = _msg_learner(organisation)
        _msg_conversation(_msg_educator(organisation), learner.user)
        learner.is_active = False
        learner.save()

        document = _tab_document(msg_client_for(admin), learner)

        assert "No other educator conversations." in document.text_content()

    def test_the_list_renders_when_the_admins_own_area_is_hidden(
        self, msg_client_for, monkeypatch
    ):
        organisation = OrganisationFactory()
        admin = _msg_educator(organisation)
        colleague = _msg_educator(organisation)
        learner = _msg_learner(organisation)
        _msg_conversation(colleague, learner.user)
        monkeypatch.setattr(
            "freedom_ls.educator_interface.panels.learner.messages.own_conversation_with",
            lambda request, learner: OwnConversation(None, False),
        )

        document = _tab_document(msg_client_for(admin), learner)

        assert not document.xpath("//form[@id='composer']")
        assert colleague.display_name in document.text_content()

    def test_the_first_send_creates_the_conversation_and_rerenders_the_tab(
        self, msg_client_for
    ):
        organisation = OrganisationFactory()
        educator = _msg_educator(organisation)
        learner = _msg_learner(organisation)

        response = msg_client_for(educator).post(
            _send_url(learner), {"body": "Welcome aboard", "client_key": str(uuid4())}
        )

        assert response.status_code == 200
        assert "HX-Location" not in response
        assert json.loads(response["HX-Trigger"]) == {"conversationChanged": {}}
        conversation = inbox_for(educator).get()
        assert conversation.messages.get().body == "Welcome aboard"
        page = lxml.html.fromstring(response.content.decode())
        assert "Welcome aboard" in page.xpath("//*[@id='thread-log']")[0].text_content()

    def test_a_reply_into_an_existing_conversation_rerenders_the_tab(
        self, msg_client_for
    ):
        organisation = OrganisationFactory()
        educator = _msg_educator(organisation)
        learner = _msg_learner(organisation)
        conversation = _msg_conversation(educator, learner.user)

        response = msg_client_for(educator).post(
            _send_url(learner), {"body": "Second thoughts", "client_key": str(uuid4())}
        )

        assert response.status_code == 200
        assert "HX-Location" not in response
        assert json.loads(response["HX-Trigger"]) == {"conversationChanged": {}}
        assert conversation.messages.get().body == "Second thoughts"
        page = lxml.html.fromstring(response.content.decode())
        assert page.xpath("//*[@id='thread-log']")

    def test_a_refused_send_answers_422_with_the_draft_and_the_alert(
        self, msg_client_for, monkeypatch
    ):
        organisation = OrganisationFactory()
        educator = _msg_educator(organisation)
        learner = _msg_learner(organisation)
        monkeypatch.setattr(
            "freedom_ls.educator_interface.panels.learner.messages.send_message",
            lambda **kwargs: SendResult(refusal=MessagingRefusal.NO_RELATIONSHIP),
        )

        response = msg_client_for(educator).post(
            _send_url(learner), {"body": "Welcome aboard", "client_key": str(uuid4())}
        )

        assert response.status_code == 422
        page = lxml.html.fromstring(response.content.decode())
        assert page.xpath("//*[@role='alert'][not(@x-show)]")
        textarea = page.xpath("//textarea[@name='body']")[0]
        assert "Welcome aboard" in textarea.text_content()
        assert not inbox_for(educator).exists()

    def test_a_first_send_refused_after_starting_closed_keeps_the_draft_and_the_alert(
        self, msg_client_for, monkeypatch
    ):
        organisation = OrganisationFactory()
        educator = _msg_educator(organisation)
        learner = _msg_learner(organisation)
        monkeypatch.setattr(
            "freedom_ls.educator_interface.panels.learner.messages.own_conversation_with",
            lambda request, learner: OwnConversation(None, False),
        )
        monkeypatch.setattr(
            "freedom_ls.educator_interface.panels.learner.messages.send_message",
            lambda **kwargs: SendResult(refusal=MessagingRefusal.NO_RELATIONSHIP),
        )

        response = msg_client_for(educator).post(
            _send_url(learner), {"body": "Welcome aboard", "client_key": str(uuid4())}
        )

        assert response.status_code == 422
        page = lxml.html.fromstring(response.content.decode())
        assert page.xpath("//*[@role='alert'][not(@x-show)]")
        textarea = page.xpath("//textarea[@name='body']")[0]
        assert "Welcome aboard" in textarea.text_content()

    def test_a_post_with_messaging_off_is_denied_and_stores_nothing(
        self, msg_client_for, settings
    ):
        organisation = OrganisationFactory()
        educator = _msg_educator(organisation)
        learner = _msg_learner(organisation)
        settings.MESSAGING_ENABLED = False

        response = msg_client_for(educator).post(
            _send_url(learner), {"body": "Welcome aboard", "client_key": str(uuid4())}
        )

        assert response.status_code in {403, 404}
        assert not inbox_for(educator).exists()


def _read_markers(conversation: Conversation) -> list[str]:
    return sorted(str(p.last_read_at) for p in conversation.participants.all())


@pytest.mark.django_db
@messages_section
class TestOversight:
    @pytest.fixture
    def scene(self):
        return _oversight_scene()

    def test_the_oversight_dialog_ends_in_a_close_button(self, msg_client_for, scene):
        organisation, _educator, learner, conversation = scene
        admin = _msg_educator(organisation)

        response = _open_conversation(msg_client_for(admin), learner, conversation.pk)

        page = lxml.html.fromstring(response.content.decode())
        assert [b.text_content().strip() for b in page.cssselect("footer button")][
            -1:
        ] == ["Close"]

    def test_the_oversight_dialog_has_one_header_and_its_thread_sits_on_the_dialog_padding(
        self, msg_client_for, scene
    ):
        """The dialog used to repeat the person in a pane header under its own
        title, and the thread and banner sat 8px left of the title."""
        organisation, _educator, learner, conversation = scene
        admin = _msg_educator(organisation)

        response = _open_conversation(msg_client_for(admin), learner, conversation.pk)

        page = lxml.html.fromstring(response.content.decode())
        assert len(page.xpath("//header")) == 1
        (pane,) = page.xpath("//section[@x-data='conversationThread']")
        assert "[&_[data-inset]]:px-6" in pane.get("class").split()
        (log,) = pane.xpath(".//*[@role='log']")
        assert "px-4" not in log.get("class").split()
        (banner,) = pane.xpath(".//*[@role='status']/..")
        assert "border-t" not in banner.get("class").split()
        assert "px-4" not in banner.get("class").split()

    def test_an_organisation_admin_reads_the_thread_read_only(
        self, msg_client_for, scene
    ):
        organisation, educator, learner, conversation = scene
        admin = _msg_educator(organisation)

        response = _open_conversation(msg_client_for(admin), learner, conversation.pk)

        assert response.status_code == 200
        page = lxml.html.fromstring(response.content.decode())
        text = " ".join(page.text_content().split())
        assert "oversight me" in text
        assert f"Conversation with {educator.display_name}" in text
        assert (
            "Read only. You are viewing this conversation as an organisation admin."
            in text
        )
        assert not page.xpath("//*[@id='composer']")

    def test_a_site_admin_is_named_as_one(
        self, msg_client_for, scene, mock_site_context
    ):
        _, _, learner, conversation = scene
        site_admin = cast(User, UserFactory(staff=True))
        _grant(site_admin, "site_admin", mock_site_context)

        response = _open_conversation(
            msg_client_for(site_admin), learner, conversation.pk
        )

        assert "as a site admin." in " ".join(response.content.decode().split())

    def test_the_open_writes_one_entry_naming_the_learner(self, msg_client_for, scene):
        organisation, educator, learner, conversation = scene
        admin = _msg_educator(organisation)

        _open_conversation(msg_client_for(admin), learner, conversation.pk)

        (entry,) = _viewed_entries()
        assert entry.target_label == f"Conversation with {educator.display_name}"
        assert entry.actor == admin
        assert entry.organisation == organisation
        assert entry.target == conversation
        assert subject_key(learner) in entry.subjects

    def test_a_second_open_writes_a_second_entry(self, msg_client_for, scene):
        organisation, _, learner, conversation = scene
        client = msg_client_for(_msg_educator(organisation))

        _open_conversation(client, learner, conversation.pk)
        _open_conversation(client, learner, conversation.pk)

        assert len(_viewed_entries()) == 2

    def test_the_open_moves_no_read_marker(self, msg_client_for, scene):
        organisation, _, learner, conversation = scene
        before = _read_markers(conversation)

        _open_conversation(
            msg_client_for(_msg_educator(organisation)), learner, conversation.pk
        )

        assert _read_markers(conversation) == before

    def test_the_entry_shows_on_the_learners_history_tab(self, msg_client_for, scene):
        organisation, _, learner, conversation = scene
        client = msg_client_for(_msg_educator(organisation))
        _open_conversation(client, learner, conversation.pk)

        text = _learner_page(client, learner, "history").text_content()

        assert "Conversation viewed" in text

    def test_a_plain_get_is_404_and_writes_nothing(self, msg_client_for, scene):
        organisation, _, learner, conversation = scene
        client = msg_client_for(_msg_educator(organisation))

        response = client.get(
            f"{_view_conversation_url(learner)}?conversation={conversation.pk}"
        )

        assert response.status_code == 404
        assert _viewed_entries() == []

    def test_a_conversation_outside_the_oversight_set_is_404(
        self, msg_client_for, scene
    ):
        organisation, _, learner, _ = scene
        client = msg_client_for(_msg_educator(organisation))
        peer = _msg_learner(organisation, first_name="Peer")
        peer_conversation = _msg_conversation(peer.user, learner.user)
        stranger = _msg_learner(OrganisationFactory())
        foreign = _msg_conversation(_msg_educator(stranger.organisation), stranger.user)

        for target in (peer_conversation.pk, foreign.pk, uuid4(), "not-a-uuid", ""):
            response = _open_conversation(client, learner, target)
            assert response.status_code == 404, target
        assert _viewed_entries() == []

    def test_the_viewers_own_conversation_is_404_and_writes_nothing(
        self, msg_client_for, scene
    ):
        _, educator, learner, conversation = scene
        client = msg_client_for(educator)

        opened = _open_conversation(client, learner, conversation.pk)
        older = client.get(
            _older_url(
                learner, conversation.pk, encode_cursor(conversation.messages.get())
            ),
            HTTP_HX_REQUEST="true",
        )

        assert opened.status_code == 404
        assert older.status_code == 404
        assert _viewed_entries() == []

    def test_a_cohort_admin_is_denied_and_nothing_is_written(
        self, msg_client_for, scene
    ):
        organisation, _, learner, conversation = scene
        cohort = CohortFactory(organisation=organisation)
        CohortMembershipFactory(cohort=cohort, learner=learner)
        cohort_admin = cast(User, UserFactory(staff=True))
        _grant(cohort_admin, "cohort_admin", cohort)

        response = _open_conversation(
            msg_client_for(cohort_admin), learner, conversation.pk
        )

        # The panel that holds the action is not shown to them, so its
        # address is a 404 like any other out-of-scope path.
        assert response.status_code == 404
        assert _viewed_entries() == []

    def test_the_action_is_denied_when_messaging_is_off(
        self, msg_client_for, scene, settings
    ):
        organisation, _, learner, conversation = scene
        client = msg_client_for(_msg_educator(organisation))
        settings.MESSAGING_ENABLED = False

        response = _open_conversation(client, learner, conversation.pk)

        assert response.status_code in (403, 404)
        assert _viewed_entries() == []

    def test_a_post_is_404(self, msg_client_for, scene):
        organisation, _, learner, conversation = scene
        client = msg_client_for(_msg_educator(organisation))

        response = client.post(
            _view_conversation_url(learner),
            {"conversation": str(conversation.pk)},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 404
        assert _viewed_entries() == []

    def test_the_list_rows_open_the_conversation_in_the_modal(
        self, msg_client_for, scene
    ):
        organisation, _, learner, conversation = scene
        admin = _msg_educator(organisation)

        document = _tab_document(msg_client_for(admin), learner)

        (row,) = document.xpath("//section[@data-panel='others']//li/button")
        assert row.get("hx-get") == (
            f"{_view_conversation_url(learner)}?conversation={conversation.pk}"
        )
        assert row.get("hx-target") == "#app-modal-body"
