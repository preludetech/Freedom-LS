"""The thread page and the send endpoint."""

from __future__ import annotations

import json
import uuid
from datetime import timedelta
from typing import cast
from urllib.parse import quote

import pytest
from lxml import html

from django.conf import settings as django_settings
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.comms.factories import ConversationFactory, MessageFactory
from freedom_ls.comms.messaging import (
    encode_cursor,
    inbox_for,
    mark_conversation_read,
)
from freedom_ls.comms.messaging_policy import (
    MessagingDecision,
    MessagingPolicy,
    MessagingRefusal,
)
from freedom_ls.comms.models import Conversation, ConversationParticipant, Message
from freedom_ls.site_aware_models.models import _thread_locals


class AllowPolicy(MessagingPolicy):
    def can_start(self, *, sender, recipient, site):
        return MessagingDecision.allow()

    def can_reply(self, *, sender, recipient, site, conversation):
        return MessagingDecision.allow()

    def recipients_for(self, *, sender, site):
        return User.objects.exclude(pk=sender.pk)


class ClosedPolicy(MessagingPolicy):
    def can_start(self, *, sender, recipient, site):
        return MessagingDecision.refuse(MessagingRefusal.CLOSED_BY_CONFIGURATION)

    def can_reply(self, *, sender, recipient, site, conversation):
        return MessagingDecision.refuse(MessagingRefusal.CLOSED_BY_CONFIGURATION)

    def recipients_for(self, *, sender, site):
        return User.objects.none()


class OnlyPolicy(AllowPolicy):
    """Allows messaging one chosen user: the class attribute ``only_pk``."""

    only_pk: int | None = None

    def can_start(self, *, sender, recipient, site):
        if recipient.pk != self.only_pk:
            return MessagingDecision.refuse(MessagingRefusal.NO_RELATIONSHIP)
        return MessagingDecision.allow()

    def recipients_for(self, *, sender, site):
        return User.objects.filter(pk=self.only_pk)


@pytest.fixture
def allow_policy(settings) -> None:
    settings.MESSAGING_POLICY = f"{__name__}.AllowPolicy"


@pytest.fixture
def closed_policy(settings) -> None:
    settings.MESSAGING_POLICY = f"{__name__}.ClosedPolicy"


@pytest.fixture
def no_relationship_policy(settings) -> None:
    settings.MESSAGING_POLICY = f"{__name__}.NoRelationshipReplyPolicy"


def name_of(user: User) -> str:
    return str(user.first_name or user.display_name)


def thread_url(conversation) -> str:
    return reverse("conversations:thread", kwargs={"pk": conversation.pk})


def send_url(conversation) -> str:
    return reverse("conversations:send", kwargs={"pk": conversation.pk})


@pytest.fixture
def pair(mock_site_context):
    user, other = UserFactory(), UserFactory()
    return user, other, ConversationFactory(between=(user, other))


HTMX = {"HTTP_HX_REQUEST": "true"}


@pytest.mark.django_db
class TestThreadAccess:
    def test_a_participant_can_open_the_thread(self, pair, logged_in_client) -> None:
        user, _, conversation = pair

        response = logged_in_client(user).get(thread_url(conversation))

        assert response.status_code == 200

    def test_a_non_participant_gets_404(self, pair, logged_in_client) -> None:
        _, _, conversation = pair

        response = logged_in_client(UserFactory()).get(thread_url(conversation))

        assert response.status_code == 404

    def test_another_sites_conversation_gets_404(
        self, mock_site_context, logged_in_client
    ) -> None:
        user, other = UserFactory(), UserFactory()
        other_site = SiteFactory()
        saved = _thread_locals.request
        saved._cached_site = other_site
        conversation = ConversationFactory(between=(user, other), site=other_site)
        saved._cached_site = mock_site_context

        response = logged_in_client(user).get(thread_url(conversation))

        assert response.status_code == 404

    def test_thread_is_404_when_messaging_is_off(
        self, pair, logged_in_client, settings
    ) -> None:
        user, _, conversation = pair
        settings.MESSAGING_ENABLED = False

        response = logged_in_client(user).get(thread_url(conversation))

        assert response.status_code == 404

    def test_send_is_404_for_a_non_participant(self, pair, logged_in_client) -> None:
        _, _, conversation = pair

        response = logged_in_client(UserFactory()).post(
            send_url(conversation),
            {"body": "Hi", "client_key": str(uuid.uuid4())},
        )

        assert response.status_code == 404

    def test_send_is_404_when_messaging_is_off(
        self, pair, logged_in_client, settings
    ) -> None:
        user, _, conversation = pair
        settings.MESSAGING_ENABLED = False

        response = logged_in_client(user).post(
            send_url(conversation), {"body": "Hi", "client_key": str(uuid.uuid4())}
        )

        assert response.status_code == 404


@pytest.mark.django_db
class TestThreadPage:
    def test_the_log_has_its_role_and_label(self, pair, logged_in_client) -> None:
        user, other, conversation = pair
        other.first_name, other.last_name = "Kai", "Ngata"
        other.save()

        response = logged_in_client(user).get(thread_url(conversation))

        log = html.fromstring(response.content).get_element_by_id("thread-log")
        assert log.get("role") == "log"
        assert log.get("aria-label") == "Messages with Kai Ngata"

    def test_messages_appear_in_the_log(self, pair, logged_in_client) -> None:
        user, other, conversation = pair
        MessageFactory(conversation=conversation, sender=other, body="Welcome aboard")

        response = logged_in_client(user).get(thread_url(conversation))

        assert "Welcome aboard" in response.content.decode()

    @pytest.mark.usefixtures("allow_policy")
    def test_the_composer_posts_once_per_click(self, pair, logged_in_client) -> None:
        user, _, conversation = pair

        response = logged_in_client(user).get(thread_url(conversation))

        tree = html.fromstring(response.content)
        composer = tree.get_element_by_id("composer")
        button = composer.xpath(".//button[@type='submit']")[0]
        assert composer.get("hx-sync") == "this:drop"
        assert button.get("hx-disabled-elt") == "this"
        assert button.get("aria-label") == "Send"

    @pytest.mark.usefixtures("allow_policy")
    def test_the_composer_is_labelled_with_the_name(
        self, pair, logged_in_client
    ) -> None:
        user, other, conversation = pair
        other.first_name = "Kai"
        other.save()

        response = logged_in_client(user).get(thread_url(conversation))

        label = html.fromstring(response.content).xpath("//label[@for='message-body']")
        assert label[0].text_content().strip() == "Message to Kai"

    @pytest.mark.usefixtures("allow_policy")
    def test_the_composer_carries_the_limit_and_counter_threshold(
        self, pair, logged_in_client
    ) -> None:
        user, _, conversation = pair

        response = logged_in_client(user).get(thread_url(conversation))

        composer = html.fromstring(response.content).get_element_by_id("composer")
        assert composer.get("data-max-length") == "2000"
        assert composer.get("data-counter-from") == "1800"

    @pytest.mark.usefixtures("allow_policy")
    def test_the_composer_shows_the_shortcut_hint(self, pair, logged_in_client) -> None:
        user, _, conversation = pair

        response = logged_in_client(user).get(thread_url(conversation))

        composer = html.fromstring(response.content).get_element_by_id("composer")
        assert "Ctrl+Enter to send" in composer.text_content()

    @pytest.mark.usefixtures("allow_policy")
    def test_the_composer_has_a_hidden_counter_and_network_alert(
        self, pair, logged_in_client
    ) -> None:
        user, _, conversation = pair

        response = logged_in_client(user).get(thread_url(conversation))

        composer = html.fromstring(response.content).get_element_by_id("composer")
        counter = composer.xpath(".//*[@aria-live='polite'][@x-show='showCounter']")
        assert counter
        failed = composer.xpath(".//*[@x-show='failed']")[0]
        assert failed.xpath(".//*[@role='alert']")
        assert "Not sent. Check your connection and try again." in (
            failed.text_content()
        )
        assert failed.xpath(".//button[normalize-space()='Retry']")

    @pytest.mark.parametrize(
        ("body", "absent"),
        [
            ("<script>alert(1)</script>", "<script>alert(1)"),
            ('<img src=x onerror="boom()">', "<img src=x"),
        ],
    )
    def test_html_in_a_body_is_escaped(
        self, pair, logged_in_client, body, absent
    ) -> None:
        user, other, conversation = pair
        MessageFactory(conversation=conversation, sender=other, body=body)

        content = logged_in_client(user).get(thread_url(conversation)).content.decode()

        assert absent not in content

    def test_a_javascript_url_is_not_linked(self, pair, logged_in_client) -> None:
        user, other, conversation = pair
        MessageFactory(
            conversation=conversation, sender=other, body="javascript:alert(1)"
        )

        response = logged_in_client(user).get(thread_url(conversation))

        entry = html.fromstring(response.content).get_element_by_id(
            f"msg-{Message.objects.get().pk}"
        )
        assert entry.xpath(".//a") == []

    def test_a_web_address_is_linked_with_nofollow(
        self, pair, logged_in_client
    ) -> None:
        user, other, conversation = pair
        MessageFactory(
            conversation=conversation,
            sender=other,
            body="see https://example.com/a?b=1&c=2",
        )

        response = logged_in_client(user).get(thread_url(conversation))

        link = html.fromstring(response.content).xpath("//ol[@id='thread-log']//a")[0]
        assert link.get("href") == "https://example.com/a?b=1&c=2"
        assert link.get("rel") == "nofollow"

    def test_an_email_address_becomes_a_mailto_link(
        self, pair, logged_in_client
    ) -> None:
        user, other, conversation = pair
        MessageFactory(
            conversation=conversation, sender=other, body="mail kai@example.com"
        )

        response = logged_in_client(user).get(thread_url(conversation))

        link = html.fromstring(response.content).xpath("//ol[@id='thread-log']//a")[0]
        assert link.get("href") == "mailto:kai@example.com"

    def test_newlines_become_line_breaks(self, pair, logged_in_client) -> None:
        user, other, conversation = pair
        MessageFactory(conversation=conversation, sender=other, body="one\ntwo")

        response = logged_in_client(user).get(thread_url(conversation))

        assert (
            len(html.fromstring(response.content).xpath("//ol[@id='thread-log']//br"))
            == 1
        )

    @pytest.mark.parametrize("body", ["{{ 7*7 }}", "{% load static %}"])
    def test_template_syntax_in_a_body_renders_literally(
        self, pair, logged_in_client, body
    ) -> None:
        user, other, conversation = pair
        MessageFactory(conversation=conversation, sender=other, body=body)

        content = logged_in_client(user).get(thread_url(conversation)).content.decode()

        assert body in content

    def test_a_deleted_sender_shows_as_deleted_user(
        self, pair, logged_in_client
    ) -> None:
        user, other, conversation = pair
        MessageFactory(conversation=conversation, sender=other, body="Bye")
        other.delete()

        content = logged_in_client(user).get(thread_url(conversation)).content.decode()

        assert "Deleted user" in content
        assert "Bye" in content


@pytest.mark.django_db
@pytest.mark.usefixtures("allow_policy")
class TestSend:
    def test_a_success_returns_the_entry_and_a_new_composer(
        self, pair, logged_in_client
    ) -> None:
        user, _, conversation = pair
        old_key = str(uuid.uuid4())

        response = logged_in_client(user).post(
            send_url(conversation), {"body": "Hello", "client_key": old_key}, **HTMX
        )

        tree = html.fromstring(f"<div>{response.content.decode()}</div>")
        message = Message.objects.get()
        assert response.status_code == 200
        assert tree.xpath(f"//li[@id='msg-{message.pk}']")
        composer = tree.xpath("//form[@id='composer']")[0]
        assert composer.get("hx-swap-oob") == "outerHTML:#composer"
        new_key = composer.xpath(".//input[@name='client_key']")[0].get("value")
        assert new_key != old_key

    def test_a_plain_post_redirects_to_the_thread(self, pair, logged_in_client) -> None:
        user, _, conversation = pair

        response = logged_in_client(user).post(
            send_url(conversation), {"body": "Hello", "client_key": str(uuid.uuid4())}
        )

        assert response.status_code == 302
        assert response["Location"] == thread_url(conversation)

    def test_a_bad_client_key_is_400(self, pair, logged_in_client) -> None:
        user, _, conversation = pair
        data = {"body": "Hello", "client_key": "not-a-uuid"}  # pragma: allowlist secret

        response = logged_in_client(user).post(send_url(conversation), data, **HTMX)

        assert response.status_code == 400

    def test_a_blank_body_returns_422_with_the_alert_and_retarget(
        self, pair, logged_in_client
    ) -> None:
        user, _, conversation = pair
        key = str(uuid.uuid4())

        response = logged_in_client(user).post(
            send_url(conversation), {"body": "  ", "client_key": key}, **HTMX
        )

        assert response.status_code == 422
        assert response["HX-Retarget"] == "#composer"
        assert response["HX-Reswap"] == "outerHTML"
        assert Message.objects.count() == 0

    def test_a_double_post_stores_one_message(self, pair, logged_in_client) -> None:
        user, _, conversation = pair
        client = logged_in_client(user)
        data = {"body": "Hello", "client_key": str(uuid.uuid4())}

        client.post(send_url(conversation), data, **HTMX)
        client.post(send_url(conversation), data, **HTMX)

        assert Message.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.usefixtures("closed_policy")
class TestSendRefused:
    def test_a_refusal_returns_422_with_the_draft_and_same_key(
        self, pair, logged_in_client
    ) -> None:
        user, _, conversation = pair
        key = str(uuid.uuid4())

        response = logged_in_client(user).post(
            send_url(conversation), {"body": "Draft text", "client_key": key}, **HTMX
        )

        tree = html.fromstring(f"<div>{response.content.decode()}</div>")
        composer = tree.xpath("//form[@id='composer']")[0]
        assert response.status_code == 422
        assert response["HX-Retarget"] == "#composer"
        assert response["HX-Reswap"] == "outerHTML"
        assert composer.xpath(".//textarea")[0].text == "Draft text"
        assert composer.xpath(".//input[@name='client_key']")[0].get("value") == key
        assert composer.xpath(".//*[@role='alert']")
        assert not tree.xpath("//li")

    def test_a_refusal_stores_nothing(self, pair, logged_in_client) -> None:
        user, _, conversation = pair

        logged_in_client(user).post(
            send_url(conversation),
            {"body": "Draft", "client_key": str(uuid.uuid4())},
            **HTMX,
        )

        assert Message.objects.count() == 0


def inbox_url() -> str:
    return reverse("conversations:inbox")


def last_read_at(conversation, user):
    return ConversationParticipant.objects.get(
        conversation=conversation, user=user
    ).last_read_at


@pytest.mark.django_db
class TestInbox:
    def test_it_lists_the_users_conversations_newest_first(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        older_other = UserFactory(first_name="Older", last_name="Person")
        newer_other = UserFactory(first_name="Newer", last_name="Person")
        MessageFactory(conversation=ConversationFactory(between=(user, older_other)))
        MessageFactory(conversation=ConversationFactory(between=(user, newer_other)))

        content = logged_in_client(user).get(inbox_url()).content.decode()

        assert content.index("Newer Person") < content.index("Older Person")

    def test_it_omits_other_peoples_conversations(
        self, mock_site_context, logged_in_client, allow_policy
    ) -> None:
        user, a, b = UserFactory(), UserFactory(), UserFactory()
        MessageFactory(
            conversation=ConversationFactory(between=(a, b)), body="Not for you"
        )

        response = logged_in_client(user).get(inbox_url())

        assert "No conversations yet." in response.content.decode()

    def test_an_unread_row_carries_the_marker_and_a_read_row_does_not(
        self, mock_site_context, logged_in_client
    ) -> None:
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        message = MessageFactory(conversation=conversation, sender=other)

        unread = logged_in_client(user).get(inbox_url()).content.decode()
        mark_conversation_read(
            user=user, conversation=conversation, up_to=message.created_at
        )
        read = logged_in_client(user).get(inbox_url()).content.decode()

        assert "Unread" in unread
        assert "Unread" not in read

    def test_rows_link_to_their_threads(
        self, mock_site_context, logged_in_client
    ) -> None:
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))

        content = logged_in_client(user).get(inbox_url()).content.decode()

        assert thread_url(conversation) in content

    def test_a_deleted_participant_shows_as_deleted_user(
        self, mock_site_context, logged_in_client
    ) -> None:
        user, other = UserFactory(), UserFactory()
        MessageFactory(conversation=ConversationFactory(between=(user, other)))
        other.delete()

        content = logged_in_client(user).get(inbox_url()).content.decode()

        assert "Deleted user" in content

    def test_it_is_404_when_messaging_is_off(
        self, mock_site_context, logged_in_client, settings
    ) -> None:
        settings.MESSAGING_ENABLED = False

        response = logged_in_client(UserFactory()).get(inbox_url())

        assert response.status_code == 404

    def test_an_anonymous_request_redirects_to_login_with_next_set_to_the_inbox(
        self, client, pair
    ) -> None:
        _, _, conversation = pair

        response = client.get(thread_url(conversation))

        assert response.status_code == 302
        assert response["Location"] == f"{django_settings.LOGIN_URL}?next={inbox_url()}"

    def test_the_fragment_has_no_page_wrapper(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        response = logged_in_client(user).get(inbox_url(), **HTMX)

        content = response.content.decode()
        assert 'id="conversation-list"' in content
        assert "<html" not in content

    def test_a_history_restore_gets_the_full_page(
        self, mock_site_context, logged_in_client
    ) -> None:
        response = logged_in_client(UserFactory()).get(
            inbox_url(), **HTMX, HTTP_HX_HISTORY_RESTORE_REQUEST="true"
        )

        assert "<html" in response.content.decode()

    @pytest.mark.usefixtures("allow_policy")
    def test_the_query_count_does_not_grow_with_the_rows(
        self, mock_site_context, logged_in_client, django_assert_max_num_queries
    ) -> None:
        user = UserFactory()
        for _ in range(8):
            MessageFactory(
                conversation=ConversationFactory(between=(user, UserFactory()))
            )
        client = logged_in_client(user)
        client.get(inbox_url())

        with django_assert_max_num_queries(15) as small:
            client.get(inbox_url())
        for _ in range(8):
            MessageFactory(
                conversation=ConversationFactory(between=(user, UserFactory()))
            )
        with django_assert_max_num_queries(len(small.captured_queries)):
            client.get(inbox_url())


@pytest.mark.django_db
class TestThreadMarksRead:
    def test_opening_a_thread_marks_the_newest_shown_message_read(
        self, pair, logged_in_client
    ) -> None:
        user, other, conversation = pair
        MessageFactory(conversation=conversation, sender=other)
        newest = MessageFactory(conversation=conversation, sender=other)

        logged_in_client(user).get(thread_url(conversation))

        assert last_read_at(conversation, user) == newest.created_at

    def test_an_empty_thread_leaves_the_marker_alone(
        self, pair, logged_in_client
    ) -> None:
        user, _, conversation = pair

        logged_in_client(user).get(thread_url(conversation))

        assert last_read_at(conversation, user) is None

    def test_a_message_landing_after_the_page_loaded_stays_unread(
        self, pair, logged_in_client
    ) -> None:
        user, other, conversation = pair
        MessageFactory(conversation=conversation, sender=other)
        logged_in_client(user).get(thread_url(conversation))

        MessageFactory(conversation=conversation, sender=other)

        assert inbox_for(user).get(pk=conversation.pk).is_unread is True

    def test_the_thread_lists_the_inbox_and_marks_the_open_row(
        self, pair, logged_in_client
    ) -> None:
        user, _, conversation = pair

        content = logged_in_client(user).get(thread_url(conversation)).content.decode()

        assert 'id="conversation-list"' in content
        assert 'aria-current="page"' in content

    def test_the_thread_has_a_back_link_to_the_inbox(
        self, pair, logged_in_client
    ) -> None:
        user, _, conversation = pair

        content = logged_in_client(user).get(thread_url(conversation)).content.decode()

        assert f'href="{inbox_url()}"' in content
        assert "Back to messages" in content


def unread_badge_url() -> str:
    return reverse("conversations:unread_badge")


@pytest.mark.django_db
class TestUnreadBadge:
    def test_it_shows_the_unread_count(self, pair, logged_in_client) -> None:
        user, other, conversation = pair
        MessageFactory(conversation=conversation, sender=other)

        content = (
            logged_in_client(user).get(unread_badge_url(), **HTMX).content.decode()
        )

        assert "Messages, 1 unread" in content

    def test_it_says_none_unread_when_everything_is_read(
        self, pair, logged_in_client
    ) -> None:
        user, _, _ = pair

        content = (
            logged_in_client(user).get(unread_badge_url(), **HTMX).content.decode()
        )

        assert "Messages, none unread" in content
        assert "hidden" in content

    def test_it_caps_the_displayed_count(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        for _ in range(100):
            other = UserFactory()
            MessageFactory(
                conversation=ConversationFactory(between=(user, other)), sender=other
            )

        content = (
            logged_in_client(user).get(unread_badge_url(), **HTMX).content.decode()
        )

        assert "99+" in content

    def test_it_is_404_when_messaging_is_off(
        self, mock_site_context, logged_in_client, settings
    ) -> None:
        settings.MESSAGING_ENABLED = False

        response = logged_in_client(UserFactory()).get(unread_badge_url(), **HTMX)

        assert response.status_code == 404


def start_url() -> str:
    return reverse("conversations:start")


@pytest.mark.django_db
@pytest.mark.usefixtures("allow_policy")
class TestStartPage:
    def test_a_known_recipient_shows_the_to_line_and_composer(
        self, mock_site_context, logged_in_client
    ) -> None:
        user = UserFactory()
        other = UserFactory(first_name="Kai", last_name="Ngata")

        response = logged_in_client(user).get(start_url(), {"recipient": other.pk})

        tree = html.fromstring(response.content)
        assert response.status_code == 200
        assert tree.xpath("//main//h1")[0].text_content().strip() == "New message"
        assert "To Kai Ngata" in " ".join(tree.text_content().split())
        change = tree.xpath("//a[normalize-space()='Change']")[0]
        assert change.get("href") == start_url()
        composer = tree.get_element_by_id("composer")
        assert composer.get("action") == start_url()
        assert composer.xpath(".//input[@name='recipient']")[0].get("value") == str(
            other.pk
        )

    def test_without_a_recipient_it_renders_the_picker_and_no_composer(
        self, mock_site_context, logged_in_client
    ) -> None:
        response = logged_in_client(UserFactory()).get(start_url())

        tree = html.fromstring(response.content)
        assert response.status_code == 200
        assert tree.get_element_by_id("recipient-picker").xpath(".//form")
        assert not tree.xpath("//form[@id='composer']")

    def test_a_recipient_outside_the_recipients_is_404(
        self, mock_site_context, logged_in_client, settings
    ) -> None:
        user, other, stranger = UserFactory(), UserFactory(), UserFactory()
        OnlyPolicy.only_pk = other.pk
        settings.MESSAGING_POLICY = f"{__name__}.OnlyPolicy"

        response = logged_in_client(user).get(start_url(), {"recipient": stranger.pk})

        assert response.status_code == 404

    def test_a_non_numeric_recipient_is_404(
        self, mock_site_context, logged_in_client
    ) -> None:
        response = logged_in_client(UserFactory()).get(start_url(), {"recipient": "x"})

        assert response.status_code == 404

    def test_the_page_is_404_when_messaging_is_off(
        self, mock_site_context, logged_in_client, settings
    ) -> None:
        settings.MESSAGING_ENABLED = False

        response = logged_in_client(UserFactory()).get(start_url())

        assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.usefixtures("allow_policy")
class TestStartSend:
    def post(self, client, other, **extra):
        data = {
            "recipient": other.pk,
            "body": "Hello there",
            "client_key": str(uuid.uuid4()),
        }
        return client.post(start_url(), data, **extra)

    def test_an_htmx_post_creates_the_conversation_and_answers_hx_location(
        self, mock_site_context, logged_in_client
    ) -> None:
        user, other = UserFactory(), UserFactory()

        response = self.post(logged_in_client(user), other, **HTMX)

        message = Message.objects.get()
        assert response.status_code == 204
        assert json.loads(response["HX-Location"]) == {
            "path": thread_url(message.conversation)
        }
        assert message.sender == user
        assert message.body == "Hello there"

    def test_a_plain_post_redirects_to_the_thread(
        self, mock_site_context, logged_in_client
    ) -> None:
        user, other = UserFactory(), UserFactory()

        response = self.post(logged_in_client(user), other)

        assert response.status_code == 302
        assert response["Location"] == thread_url(Message.objects.get().conversation)

    def test_a_second_post_for_the_pair_reuses_the_conversation(
        self, mock_site_context, logged_in_client
    ) -> None:
        user, other = UserFactory(), UserFactory()
        client = logged_in_client(user)

        self.post(client, other, **HTMX)
        self.post(client, other, **HTMX)

        assert Conversation.objects.count() == 1
        assert Message.objects.count() == 2

    def test_a_bad_client_key_is_400(self, mock_site_context, logged_in_client) -> None:
        other = UserFactory()
        data = {
            "recipient": other.pk,
            "body": "Hi",
            "client_key": "nope",  # pragma: allowlist secret
        }

        response = logged_in_client(UserFactory()).post(start_url(), data, **HTMX)

        assert response.status_code == 400

    def test_a_blank_body_returns_422_with_the_composer(
        self, mock_site_context, logged_in_client
    ) -> None:
        user, other = UserFactory(), UserFactory()
        data = {"recipient": other.pk, "body": " ", "client_key": str(uuid.uuid4())}

        response = logged_in_client(user).post(start_url(), data, **HTMX)

        tree = html.fromstring(f"<div>{response.content.decode()}</div>")
        assert response.status_code == 422
        assert response["HX-Retarget"] == "#composer"
        assert response["HX-Reswap"] == "outerHTML"
        composer = tree.xpath("//form[@id='composer']")[0]
        assert composer.get("action") == start_url()
        assert composer.xpath(".//input[@name='recipient']")[0].get("value") == str(
            other.pk
        )
        assert composer.xpath(".//*[@role='alert']")
        assert Conversation.objects.count() == 0

    def test_a_post_to_an_unknown_recipient_is_404(
        self, mock_site_context, logged_in_client
    ) -> None:
        data = {"recipient": 999999, "body": "Hi", "client_key": str(uuid.uuid4())}

        response = logged_in_client(UserFactory()).post(start_url(), data, **HTMX)

        assert response.status_code == 404

    def test_a_post_is_404_when_messaging_is_off(
        self, mock_site_context, logged_in_client, settings
    ) -> None:
        settings.MESSAGING_ENABLED = False

        response = self.post(logged_in_client(UserFactory()), UserFactory(), **HTMX)

        assert response.status_code == 404


@pytest.mark.django_db
class TestStartRefused:
    def test_can_start_is_asked_again_and_a_refusal_returns_422_with_the_draft(
        self, mock_site_context, logged_in_client, closed_policy
    ) -> None:
        user, other = UserFactory(), UserFactory()
        key = str(uuid.uuid4())
        data = {"recipient": other.pk, "body": "My draft", "client_key": key}

        response = logged_in_client(user).post(start_url(), data, **HTMX)

        tree = html.fromstring(f"<div>{response.content.decode()}</div>")
        composer = tree.xpath("//form[@id='composer']")[0]
        assert response.status_code == 422
        assert response["HX-Retarget"] == "#composer"
        assert composer.xpath(".//textarea")[0].text == "My draft"
        assert composer.xpath(".//input[@name='client_key']")[0].get("value") == key
        assert composer.xpath(".//*[@role='alert']")
        assert Message.objects.count() == 0

    def test_a_recipient_outside_the_recipients_is_refused(
        self, mock_site_context, logged_in_client, settings
    ) -> None:
        user, other, stranger = UserFactory(), UserFactory(), UserFactory()
        OnlyPolicy.only_pk = other.pk
        settings.MESSAGING_POLICY = f"{__name__}.OnlyPolicy"
        data = {
            "recipient": stranger.pk,
            "body": "Hi",
            "client_key": str(uuid.uuid4()),
        }

        response = logged_in_client(user).post(start_url(), data, **HTMX)

        assert response.status_code == 422
        assert Message.objects.count() == 0

    def test_a_plain_refusal_renders_the_start_page_at_422(
        self, mock_site_context, logged_in_client, closed_policy
    ) -> None:
        user, other = UserFactory(), UserFactory()
        data = {
            "recipient": other.pk,
            "body": "Draft",
            "client_key": str(uuid.uuid4()),
        }

        response = logged_in_client(user).post(start_url(), data)

        tree = html.fromstring(response.content)
        assert response.status_code == 422
        assert tree.xpath("//main//h1")[0].text_content().strip() == "New message"
        assert tree.xpath("//textarea")[0].text == "Draft"


@pytest.mark.django_db
class TestInboxNewMessage:
    def test_the_button_shows_when_the_user_has_recipients(
        self, mock_site_context, logged_in_client, allow_policy
    ) -> None:
        UserFactory()

        response = logged_in_client(UserFactory()).get(inbox_url())

        tree = html.fromstring(response.content)
        assert tree.xpath(f"//a[@href='{start_url()}']")

    def test_the_button_is_absent_without_recipients(
        self, mock_site_context, logged_in_client, closed_policy
    ) -> None:
        response = logged_in_client(UserFactory()).get(inbox_url())

        tree = html.fromstring(response.content)
        assert not tree.xpath(f"//main//a[@href='{start_url()}']")

    def test_no_recipients_reads_the_educators_copy(
        self, mock_site_context, logged_in_client, closed_policy
    ) -> None:
        response = logged_in_client(UserFactory()).get(inbox_url())

        assert (
            "Your educators can message you, and you can reply."
            in response.content.decode()
        )

    def test_recipients_read_no_conversations_yet(
        self, mock_site_context, logged_in_client, allow_policy
    ) -> None:
        UserFactory()

        response = logged_in_client(UserFactory()).get(inbox_url())

        content = response.content.decode()
        assert "No conversations yet." in content
        assert "Your educators can message you" not in content


def search_url() -> str:
    return reverse("conversations:recipient_search")


@pytest.mark.django_db
@pytest.mark.usefixtures("allow_policy")
class TestRecipientPicker:
    def test_the_start_page_fills_the_picker_with_a_search_form_and_results(
        self, mock_site_context, logged_in_client
    ) -> None:
        UserFactory(first_name="Kai", last_name="Ngata")

        response = logged_in_client(UserFactory()).get(start_url())

        tree = html.fromstring(response.content)
        picker = tree.get_element_by_id("recipient-picker")
        form = picker.xpath(".//form")[0]
        assert form.get("hx-get") == search_url()
        assert form.get("hx-sync") == "this:replace"
        assert "delay:300ms" in form.get("hx-trigger")
        assert form.xpath(".//label[@for='recipient-q']")[0].text.strip() == "To"
        assert picker.xpath(".//*[@id='recipient-results']")

    def test_results_are_grouped_and_link_to_the_composer_for_that_person(
        self, mock_site_context, logged_in_client
    ) -> None:
        kai = UserFactory(first_name="Kai", last_name="Ngata")

        response = logged_in_client(UserFactory()).get(search_url(), {"q": "kai"})

        tree = html.fromstring(response.content)
        assert tree.xpath("//*[@role='group']")
        link = tree.xpath("//a[contains(normalize-space(.), 'Kai Ngata')]")[0]
        assert link.get("href") == f"{start_url()}?recipient={kai.pk}"

    def test_the_search_fragment_has_no_page_wrapper(
        self, mock_site_context, logged_in_client
    ) -> None:
        UserFactory(first_name="Kai")

        response = logged_in_client(UserFactory()).get(search_url(), {"q": "kai"})

        content = response.content.decode()
        assert "<html" not in content
        assert content.lstrip().startswith("<div")
        assert 'id="recipient-results"' in content

    def test_an_email_is_not_shown_in_the_shared_picker(
        self, mock_site_context, logged_in_client
    ) -> None:
        UserFactory(first_name="Kai", email="kai-private@example.com")

        response = logged_in_client(UserFactory()).get(search_url(), {"q": "kai"})

        assert "kai-private@example.com" not in response.content.decode()

    def test_no_match_says_so_with_the_term(
        self, mock_site_context, logged_in_client
    ) -> None:
        response = logged_in_client(UserFactory()).get(search_url(), {"q": "zzzz"})

        assert 'No one you can message matches "zzzz"' in response.content.decode()

    def test_a_long_list_asks_for_a_term(
        self, mock_site_context, logged_in_client
    ) -> None:
        UserFactory.create_batch(16)

        response = logged_in_client(UserFactory()).get(search_url())

        assert "Keep typing" in response.content.decode()

    def test_truncated_results_say_to_keep_typing(
        self, mock_site_context, logged_in_client
    ) -> None:
        UserFactory.create_batch(21, first_name="Match")

        response = logged_in_client(UserFactory()).get(search_url(), {"q": "match"})

        assert "Keep typing to narrow the list." in response.content.decode()

    def test_the_match_count_is_announced_politely(
        self, mock_site_context, logged_in_client
    ) -> None:
        UserFactory(first_name="Kai")

        response = logged_in_client(UserFactory()).get(search_url(), {"q": "kai"})

        status = html.fromstring(response.content).xpath("//*[@role='status']")[0]
        assert status.get("aria-live") == "polite"
        assert status.text_content().strip() == "1 person found"

    def test_the_search_is_404_when_messaging_is_off(
        self, mock_site_context, logged_in_client, settings
    ) -> None:
        settings.MESSAGING_ENABLED = False

        response = logged_in_client(UserFactory()).get(search_url())

        assert response.status_code == 404

    def test_the_search_never_offers_someone_outside_the_recipients(
        self, mock_site_context, logged_in_client, settings
    ) -> None:
        user, other = UserFactory(), UserFactory(first_name="Kai", last_name="Allowed")
        UserFactory(first_name="Kai", last_name="Refused")
        OnlyPolicy.only_pk = other.pk
        settings.MESSAGING_POLICY = f"{__name__}.OnlyPolicy"

        response = logged_in_client(user).get(search_url(), {"q": "kai"})

        content = response.content.decode()
        assert "Kai Allowed" in content
        assert "Refused" not in content


@pytest.mark.django_db
@pytest.mark.usefixtures("allow_policy")
def test_the_start_page_renders_the_results_region_once(
    mock_site_context, logged_in_client
) -> None:
    UserFactory(first_name="Kai", last_name="Ngata")

    response = logged_in_client(UserFactory()).get(start_url())

    tree = html.fromstring(response.content)
    assert len(tree.xpath("//*[@id='recipient-results']")) == 1
    assert len(tree.xpath("//a[contains(., 'Kai Ngata')]")) == 1


@pytest.mark.django_db
@pytest.mark.usefixtures("closed_policy")
class TestClosedThread:
    def test_the_note_replaces_the_composer(self, pair, logged_in_client) -> None:
        user, other, conversation = pair
        MessageFactory(conversation=conversation, sender=other, body="Earlier")

        response = logged_in_client(user).get(thread_url(conversation))

        tree = html.fromstring(response.content)
        note = tree.xpath("//*[@id='composer']")[0]
        assert not tree.xpath("//form[@id='composer']")
        assert not tree.xpath("//textarea")
        assert note.get("role") == "status"
        assert "Replies are closed" in note.text_content()
        assert f"Messaging between you and {name_of(other)} is closed here." in (
            note.text_content()
        )
        assert "Earlier" in response.content.decode()

    def test_a_refused_send_still_shows_the_alert_and_the_draft(
        self, pair, logged_in_client
    ) -> None:
        user, other, conversation = pair

        response = logged_in_client(user).post(
            send_url(conversation),
            {"body": "Draft", "client_key": str(uuid.uuid4())},
            **HTMX,
        )

        content = response.content.decode()
        assert response.status_code == 422
        assert f"Not sent. {name_of(other)} can&#x27;t receive messages" in content
        assert "Draft" in content

    def test_the_inbox_row_is_tagged_read_only_and_keeps_its_state(
        self, mock_site_context, logged_in_client
    ) -> None:
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        MessageFactory(conversation=conversation, sender=other)

        response = logged_in_client(user).get(inbox_url())

        tree = html.fromstring(response.content)
        row = tree.xpath(f"//li[.//a[@href='{thread_url(conversation)}']]")[0]
        assert "Read only" in row.text_content()
        assert "Unread" in row.text_content()


@pytest.mark.django_db
@pytest.mark.usefixtures("no_relationship_policy")
class TestClosedThreadNoRelationship:
    def test_a_no_relationship_refusal_uses_its_own_body(
        self, pair, logged_in_client
    ) -> None:
        user, other, conversation = pair

        content = logged_in_client(user).get(thread_url(conversation)).content.decode()

        assert f"You can no longer message {name_of(other)} from here." in content


@pytest.mark.django_db
@pytest.mark.usefixtures("allow_policy")
class TestOpenThread:
    def test_an_open_thread_has_the_composer_and_no_note(
        self, pair, logged_in_client
    ) -> None:
        user, _, conversation = pair

        tree = html.fromstring(
            logged_in_client(user).get(thread_url(conversation)).content
        )

        assert tree.xpath("//form[@id='composer']")
        assert "Replies are closed" not in tree.text_content()

    def test_an_open_inbox_row_has_no_read_only_tag(
        self, pair, logged_in_client
    ) -> None:
        user, _, _ = pair

        content = logged_in_client(user).get(inbox_url()).content.decode()

        assert "Read only" not in content


class NoRelationshipReplyPolicy(AllowPolicy):
    def can_reply(self, *, sender, recipient, site, conversation):
        return MessagingDecision.refuse(MessagingRefusal.NO_RELATIONSHIP)


class ExplodingPolicy(AllowPolicy):
    def can_reply(self, *, sender, recipient, site, conversation):
        raise AssertionError("the policy must not be asked about a deleted user")


@pytest.mark.django_db
class TestDeletedParticipantViews:
    @pytest.fixture(autouse=True)
    def _exploding_policy(self, settings) -> None:
        settings.MESSAGING_POLICY = f"{__name__}.ExplodingPolicy"

    def test_the_thread_renders_with_the_generic_closed_note(
        self, pair, logged_in_client
    ) -> None:
        user, other, conversation = pair
        MessageFactory(conversation=conversation, sender=other, body="Bye")
        other.delete()

        response = logged_in_client(user).get(thread_url(conversation))

        content = response.content.decode()
        assert response.status_code == 200
        assert "Deleted user" in content
        assert "Bye" in content
        assert "This conversation can&#x27;t take new messages." in content
        assert "<textarea" not in content

    def test_a_send_shows_the_deleted_variant_and_stores_nothing(
        self, pair, logged_in_client
    ) -> None:
        user, other, conversation = pair
        other.delete()

        response = logged_in_client(user).post(
            send_url(conversation),
            {"body": "Hello?", "client_key": str(uuid.uuid4())},
            **HTMX,
        )

        assert response.status_code == 422
        assert "Not sent. This conversation can&#x27;t take new messages." in (
            response.content.decode()
        )
        assert Message.objects.count() == 0

    def test_the_survivors_inbox_keeps_the_unread_state(
        self, pair, logged_in_client
    ) -> None:
        user, other, conversation = pair
        MessageFactory(conversation=conversation, sender=other)
        other.delete()

        row = html.fromstring(logged_in_client(user).get(inbox_url()).content).xpath(
            f"//li[.//a[@href='{thread_url(conversation)}']]"
        )[0]

        assert "Deleted user" in row.text_content()
        assert "Unread" in row.text_content()
        assert "Read only" in row.text_content()


def older_url(conversation, cursor: str) -> str:
    base = reverse("conversations:thread_older", kwargs={"pk": conversation.pk})
    return f"{base}?before={quote(cursor)}"


def stamped_message(conversation, sender, at, body="x") -> Message:
    message = MessageFactory(conversation=conversation, sender=sender, body=body)
    Message.objects.filter(pk=message.pk).update(created_at=at)
    return cast("Message", Message.objects.get(pk=message.pk))


def older_control(tree):
    return tree.xpath("//div[@id='thread-older']")[0]


@pytest.mark.django_db
class TestEarlierMessages:
    @pytest.fixture
    def long_thread(self, pair, settings):
        settings.MESSAGE_PAGE_SIZE = 3
        user, other, conversation = pair
        base = timezone.now() - timedelta(days=3)
        messages = [
            stamped_message(conversation, other, base + timedelta(minutes=i), f"m{i}")
            for i in range(7)
        ]
        return user, conversation, messages

    def test_the_thread_shows_the_control_when_older_messages_exist(
        self, long_thread, logged_in_client
    ) -> None:
        user, conversation, messages = long_thread

        response = logged_in_client(user).get(thread_url(conversation))

        tree = html.fromstring(response.content)
        button = older_control(tree).xpath(".//button")[0]
        assert button.text_content().strip() == "Load earlier messages"
        assert button.get("hx-target") == "#thread-log"
        assert button.get("hx-swap") == "afterbegin"
        assert quote(encode_cursor(messages[4])) in button.get("hx-get")
        assert not tree.xpath("//ol[@id='thread-log']//*[@id='thread-older']")

    def test_the_thread_has_no_control_when_one_page_holds_everything(
        self, pair, logged_in_client
    ) -> None:
        user, other, conversation = pair
        MessageFactory(conversation=conversation, sender=other)

        response = logged_in_client(user).get(thread_url(conversation))

        assert not older_control(html.fromstring(response.content)).xpath(".//button")

    def test_a_page_returns_the_page_size_with_the_next_control(
        self, long_thread, logged_in_client
    ) -> None:
        user, conversation, messages = long_thread

        response = logged_in_client(user).get(
            older_url(conversation, encode_cursor(messages[4])), **HTMX
        )

        tree = html.fromstring(f"<div>{response.content.decode()}</div>")
        ids = [li.get("id") for li in tree.xpath("./li[not(@hx-swap-oob)]")]
        assert ids == [f"msg-{m.pk}" for m in messages[1:4]]
        control = tree.xpath("./div[@id='thread-older']")[0]
        assert control.get("hx-swap-oob") == "outerHTML"
        assert quote(encode_cursor(messages[1])) in control.xpath(".//button")[0].get(
            "hx-get"
        )

    def test_an_exactly_full_last_page_returns_an_empty_control(
        self, long_thread, logged_in_client
    ) -> None:
        user, conversation, messages = long_thread

        response = logged_in_client(user).get(
            older_url(conversation, encode_cursor(messages[3])), **HTMX
        )

        tree = html.fromstring(f"<div>{response.content.decode()}</div>")
        assert len(tree.xpath("./li[not(@hx-swap-oob)]")) == 3
        control = tree.xpath("./div[@id='thread-older']")[0]
        assert not control.xpath(".//button")

    def test_a_malformed_cursor_is_a_400(self, long_thread, logged_in_client) -> None:
        user, conversation, _ = long_thread

        response = logged_in_client(user).get(older_url(conversation, "junk"), **HTMX)

        assert response.status_code == 400

    def test_a_missing_cursor_is_a_400(self, long_thread, logged_in_client) -> None:
        user, conversation, _ = long_thread
        url = reverse("conversations:thread_older", kwargs={"pk": conversation.pk})

        assert logged_in_client(user).get(url, **HTMX).status_code == 400

    def test_a_cursor_with_a_utc_offset_round_trips_through_the_query_string(
        self, long_thread, logged_in_client
    ) -> None:
        user, conversation, messages = long_thread
        cursor = encode_cursor(messages[4])
        assert "+00:00" in cursor

        response = logged_in_client(user).get(older_url(conversation, cursor), **HTMX)

        assert response.status_code == 200
        assert f"msg-{messages[3].pk}" in response.content.decode()

    def test_a_stranger_gets_a_404(self, long_thread, logged_in_client) -> None:
        _, conversation, messages = long_thread

        response = logged_in_client(UserFactory()).get(
            older_url(conversation, encode_cursor(messages[4])), **HTMX
        )

        assert response.status_code == 404

    def test_the_boundary_entry_loses_its_separator_when_the_page_ends_on_its_day(
        self, pair, logged_in_client, settings
    ) -> None:
        settings.MESSAGE_PAGE_SIZE = 2
        user, other, conversation = pair
        noon = timezone.now().replace(hour=12, minute=0) - timedelta(days=2)
        stamped_message(conversation, other, noon, "a")
        stamped_message(conversation, other, noon + timedelta(minutes=1), "b")
        boundary = stamped_message(
            conversation, other, noon + timedelta(minutes=2), "c"
        )
        client = logged_in_client(user)
        page = html.fromstring(client.get(thread_url(conversation)).content)
        assert (
            page.xpath(f"//li[@id='msg-{boundary.pk}']//*[@data-day-separator]") == []
        )

        response = client.get(older_url(conversation, encode_cursor(boundary)), **HTMX)

        tree = html.fromstring(f"<div>{response.content.decode()}</div>")
        redrawn = tree.xpath(f"./li[@id='msg-{boundary.pk}']")[0]
        assert redrawn.get("hx-swap-oob") == "outerHTML"
        assert not redrawn.xpath(".//*[@data-day-separator]")
        assert not redrawn.xpath(".//time")
        first = tree.xpath("./li[not(@hx-swap-oob)]")[0]
        assert first.xpath(".//*[@data-day-separator]")

    def test_the_boundary_entry_keeps_its_separator_across_a_day_change(
        self, pair, logged_in_client, settings
    ) -> None:
        settings.MESSAGE_PAGE_SIZE = 1
        user, other, conversation = pair
        noon = timezone.now().replace(hour=12, minute=0) - timedelta(days=3)
        stamped_message(conversation, other, noon, "a")
        boundary = stamped_message(conversation, other, noon + timedelta(days=1), "b")

        response = logged_in_client(user).get(
            older_url(conversation, encode_cursor(boundary)), **HTMX
        )

        tree = html.fromstring(f"<div>{response.content.decode()}</div>")
        redrawn = tree.xpath(f"./li[@id='msg-{boundary.pk}']")[0]
        assert redrawn.xpath(".//*[@data-day-separator]")

    def test_a_message_landing_during_the_load_appears_once(
        self, long_thread, logged_in_client
    ) -> None:
        user, conversation, messages = long_thread
        client = logged_in_client(user)
        cursor = encode_cursor(messages[4])
        landed = MessageFactory(conversation=conversation, body="late")

        response = client.get(older_url(conversation, cursor), **HTMX)

        assert f"msg-{landed.pk}" not in response.content.decode()
        page = client.get(thread_url(conversation)).content.decode()
        assert page.count(f"msg-{landed.pk}") == 1


def poll_url(conversation, *, after="", composer="open", draft="0") -> str:
    base = reverse("conversations:thread_poll", kwargs={"pk": conversation.pk})
    return f"{base}?after={quote(after)}&composer={composer}&draft={draft}"


def poll_tree(response):
    return html.fromstring(f"<div>{response.content.decode()}</div>")


@pytest.mark.django_db
@pytest.mark.usefixtures("allow_policy")
class TestThreadPoll:
    @pytest.fixture
    def seen(self, pair):
        """The pair with one message already on screen, and its cursor."""
        user, other, conversation = pair
        first = MessageFactory(conversation=conversation, sender=other, body="First")
        return user, other, conversation, encode_cursor(first)

    def test_the_thread_carries_the_newest_cursor_and_the_poller(
        self, seen, logged_in_client, settings
    ) -> None:
        user, _, conversation, cursor = seen
        settings.MESSAGE_THREAD_POLL_SECONDS = 5

        tree = html.fromstring(
            logged_in_client(user).get(thread_url(conversation)).content
        )

        assert tree.xpath("//input[@id='thread-cursor']")[0].get("value") == cursor
        assert tree.xpath("//input[@id='thread-cursor']")[0].get("name") == "after"
        poller = tree.xpath("//div[@x-data='refreshTimer'][.//span[@x-ref='target']]")[
            0
        ]
        assert poller.get("data-poll-seconds") == "5"
        target = poller.xpath(".//span[@x-ref='target']")[0]
        assert target.get("hx-get") == reverse(
            "conversations:thread_poll", kwargs={"pk": conversation.pk}
        )
        assert target.get("hx-target") == "#thread-log"
        assert target.get("hx-swap") == "beforeend"
        assert target.get("hx-include") == (
            "#thread-cursor, #composer-state, #composer-draft"
        )
        assert tree.xpath("//*[@id='thread-status'][@role='status']")

    def test_nothing_new_is_204_and_writes_nothing(
        self, seen, logged_in_client
    ) -> None:
        user, _, conversation, cursor = seen
        before = last_read_at(conversation, user)

        response = logged_in_client(user).get(
            poll_url(conversation, after=cursor), **HTMX
        )

        assert response.status_code == 204
        assert last_read_at(conversation, user) == before
        assert "HX-Trigger" not in response

    def test_new_messages_come_back_as_entries_with_the_cursor(
        self, seen, logged_in_client
    ) -> None:
        user, other, conversation, cursor = seen
        newer = MessageFactory(conversation=conversation, sender=other, body="Second")

        response = logged_in_client(user).get(
            poll_url(conversation, after=cursor), **HTMX
        )

        tree = poll_tree(response)
        assert response.status_code == 200
        assert [li.get("id") for li in tree.xpath("./li")] == [f"msg-{newer.pk}"]
        cursor_input = tree.xpath("./input[@id='thread-cursor']")[0]
        assert cursor_input.get("hx-swap-oob") == "outerHTML"
        assert cursor_input.get("value") == encode_cursor(newer)
        assert not tree.xpath("//form")

    def test_incoming_messages_mark_the_thread_read_and_announce_themselves(
        self, seen, logged_in_client
    ) -> None:
        user, other, conversation, cursor = seen
        MessageFactory(conversation=conversation, sender=other, body="Second")
        newest = MessageFactory(conversation=conversation, sender=other, body="Third")

        response = logged_in_client(user).get(
            poll_url(conversation, after=cursor), **HTMX
        )

        status = poll_tree(response).xpath("./*[@id='thread-status']")[0]
        assert status.get("hx-swap-oob") == "true"
        assert status.get("role") == "status"
        assert status.text_content().strip() == (
            f"2 new messages from {other.display_name}"
        )
        assert "Third" not in status.text_content()
        assert json.loads(response["HX-Trigger"]) == {"conversationChanged": {}}
        assert last_read_at(conversation, user) >= newest.created_at

    def test_one_incoming_message_is_announced_in_the_singular(
        self, seen, logged_in_client
    ) -> None:
        user, other, conversation, cursor = seen
        MessageFactory(conversation=conversation, sender=other)

        response = logged_in_client(user).get(
            poll_url(conversation, after=cursor), **HTMX
        )

        status = poll_tree(response).xpath("./*[@id='thread-status']")[0]
        assert status.text_content().strip() == (
            f"1 new message from {other.display_name}"
        )

    def test_the_viewers_own_new_message_is_an_entry_without_an_announcement(
        self, seen, logged_in_client
    ) -> None:
        user, _, conversation, cursor = seen
        mine = MessageFactory(conversation=conversation, sender=user, body="Mine")

        response = logged_in_client(user).get(
            poll_url(conversation, after=cursor), **HTMX
        )

        tree = poll_tree(response)
        assert tree.xpath(f"./li[@id='msg-{mine.pk}'][@data-own]")
        assert not tree.xpath("//*[@id='thread-status']")
        assert "HX-Trigger" not in response

    def test_an_entry_carries_data_own_only_for_the_viewers_messages(
        self, seen, logged_in_client
    ) -> None:
        user, other, conversation, cursor = seen
        theirs = MessageFactory(conversation=conversation, sender=other)

        tree = poll_tree(
            logged_in_client(user).get(poll_url(conversation, after=cursor), **HTMX)
        )

        assert not tree.xpath(f"./li[@id='msg-{theirs.pk}'][@data-own]")

    def test_new_entries_are_judged_against_the_cursor_message(
        self, seen, logged_in_client
    ) -> None:
        user, other, conversation, cursor = seen
        MessageFactory(conversation=conversation, sender=other)

        tree = poll_tree(
            logged_in_client(user).get(poll_url(conversation, after=cursor), **HTMX)
        )

        assert not tree.xpath("./li//*[@data-day-separator]")
        assert not tree.xpath("./li//time")

    def test_an_empty_cursor_returns_the_whole_thread(
        self, seen, logged_in_client
    ) -> None:
        user, _, conversation, _ = seen

        response = logged_in_client(user).get(poll_url(conversation), **HTMX)

        assert len(poll_tree(response).xpath("./li")) == 1

    def test_a_malformed_cursor_is_a_400(self, seen, logged_in_client) -> None:
        user, _, conversation, _ = seen

        response = logged_in_client(user).get(
            poll_url(conversation, after="junk"), **HTMX
        )

        assert response.status_code == 400

    def test_a_non_participant_gets_404(
        self, seen, logged_in_client, mock_site_context
    ) -> None:
        _, _, conversation, cursor = seen

        response = logged_in_client(UserFactory()).get(
            poll_url(conversation, after=cursor), **HTMX
        )

        assert response.status_code == 404

    def test_an_anonymous_htmx_poll_is_sent_to_login(self, seen, client) -> None:
        _, _, conversation, cursor = seen

        response = client.get(poll_url(conversation, after=cursor), **HTMX)

        assert response.status_code == 204
        assert "HX-Redirect" in response


@pytest.mark.django_db
class TestThreadPollComposerFlip:
    @pytest.fixture
    def seen(self, pair):
        user, other, conversation = pair
        first = MessageFactory(conversation=conversation, sender=other)
        return user, other, conversation, encode_cursor(first)

    @pytest.mark.usefixtures("closed_policy")
    def test_a_newly_closed_thread_swaps_in_the_note_when_there_is_no_draft(
        self, seen, logged_in_client
    ) -> None:
        user, _, conversation, cursor = seen

        response = logged_in_client(user).get(
            poll_url(conversation, after=cursor, composer="open", draft="0"), **HTMX
        )

        note = poll_tree(response).xpath("./div[@id='composer']")[0]
        assert response.status_code == 200
        assert note.get("hx-swap-oob") == "outerHTML:#composer"
        assert "Replies are closed" in note.text_content()

    @pytest.mark.usefixtures("closed_policy")
    def test_a_newly_closed_thread_leaves_a_drafted_composer_in_place(
        self, seen, logged_in_client
    ) -> None:
        user, _, conversation, cursor = seen

        response = logged_in_client(user).get(
            poll_url(conversation, after=cursor, composer="open", draft="1"), **HTMX
        )

        tree = poll_tree(response)
        assert not tree.xpath("//*[@id='composer']")
        assert not tree.xpath("//textarea")

    @pytest.mark.usefixtures("allow_policy")
    def test_a_reopened_thread_brings_the_composer_back(
        self, seen, logged_in_client
    ) -> None:
        user, _, conversation, cursor = seen

        response = logged_in_client(user).get(
            poll_url(conversation, after=cursor, composer="closed", draft="0"), **HTMX
        )

        composer = poll_tree(response).xpath("./form[@id='composer']")[0]
        assert composer.get("hx-swap-oob") == "outerHTML:#composer"
        assert composer.xpath(".//textarea")

    @pytest.mark.usefixtures("allow_policy")
    def test_an_open_thread_with_an_open_composer_is_not_flipped(
        self, seen, logged_in_client
    ) -> None:
        user, _, conversation, cursor = seen

        response = logged_in_client(user).get(
            poll_url(conversation, after=cursor, composer="open"), **HTMX
        )

        assert response.status_code == 204

    @pytest.mark.usefixtures("closed_policy")
    def test_a_closed_thread_with_the_note_showing_is_not_flipped(
        self, seen, logged_in_client
    ) -> None:
        user, _, conversation, cursor = seen

        response = logged_in_client(user).get(
            poll_url(conversation, after=cursor, composer="closed"), **HTMX
        )

        assert response.status_code == 204

    @pytest.mark.usefixtures("closed_policy")
    def test_new_messages_and_a_flip_arrive_in_one_response(
        self, seen, logged_in_client
    ) -> None:
        user, other, conversation, cursor = seen
        newer = MessageFactory(conversation=conversation, sender=other)

        tree = poll_tree(
            logged_in_client(user).get(
                poll_url(conversation, after=cursor, composer="open"), **HTMX
            )
        )

        assert tree.xpath(f"./li[@id='msg-{newer.pk}']")
        assert tree.xpath("./div[@id='composer']")

    @pytest.mark.usefixtures("allow_policy")
    def test_a_composer_rendered_with_text_carries_the_draft_flag(
        self, seen, logged_in_client
    ) -> None:
        user, _, conversation, _ = seen
        data = {"body": "  ", "client_key": str(uuid.uuid4())}

        response = logged_in_client(user).post(send_url(conversation), data, **HTMX)

        composer = poll_tree(response).xpath("//form[@id='composer']")[0]
        assert composer.xpath(".//input[@id='composer-draft']")[0].get("value") == "1"
        assert (
            composer.xpath(".//input[@id='composer-state']")[0].get("value") == "open"
        )

    @pytest.mark.usefixtures("allow_policy")
    def test_an_empty_composer_carries_a_zero_draft_flag(
        self, seen, logged_in_client
    ) -> None:
        user, _, conversation, _ = seen

        tree = html.fromstring(
            logged_in_client(user).get(thread_url(conversation)).content
        )

        assert tree.xpath("//input[@id='composer-draft']")[0].get("value") == "0"

    @pytest.mark.usefixtures("closed_policy")
    def test_the_closed_note_carries_the_closed_state(
        self, seen, logged_in_client
    ) -> None:
        user, _, conversation, _ = seen

        tree = html.fromstring(
            logged_in_client(user).get(thread_url(conversation)).content
        )

        assert tree.xpath("//input[@id='composer-state']")[0].get("value") == "closed"
        assert tree.xpath("//input[@id='composer-state']")[0].get("name") == "composer"
        assert tree.xpath("//input[@id='composer-draft']")[0].get("value") == "0"


@pytest.mark.django_db
@pytest.mark.usefixtures("allow_policy")
class TestSendCarriesTheThreadSignals:
    def test_a_success_sets_the_cursor_and_announces_the_change(
        self, pair, logged_in_client
    ) -> None:
        user, _, conversation = pair

        response = logged_in_client(user).post(
            send_url(conversation),
            {"body": "Hello", "client_key": str(uuid.uuid4())},
            **HTMX,
        )

        tree = poll_tree(response)
        message = Message.objects.get()
        cursor_input = tree.xpath("//input[@id='thread-cursor']")[0]
        assert cursor_input.get("hx-swap-oob") == "outerHTML"
        assert cursor_input.get("value") == encode_cursor(message)
        assert tree.xpath(f"//li[@id='msg-{message.pk}'][@data-own]")
        assert json.loads(response["HX-Trigger"]) == {"conversationChanged": {}}


def inbox_poll_url(*, since="", current="") -> str:
    base = reverse("conversations:inbox_poll")
    return f"{base}?since={quote(since)}&current={current}"


@pytest.mark.django_db
@pytest.mark.usefixtures("allow_policy")
class TestInboxPoll:
    @pytest.fixture
    def seen(self, pair):
        """The pair with one message already listed, and the inbox's marker."""
        user, other, conversation = pair
        MessageFactory(conversation=conversation, sender=other)
        conversation.refresh_from_db()
        return user, other, conversation, conversation.last_message_at.isoformat()

    def test_the_inbox_carries_the_poller_and_the_marker(
        self, seen, logged_in_client, settings
    ) -> None:
        user, _, _, since = seen
        settings.MESSAGE_INBOX_POLL_SECONDS = 7

        tree = html.fromstring(logged_in_client(user).get(inbox_url()).content)

        poller = tree.xpath("//div[@x-data='refreshTimer']")[0]
        assert poller.get("data-poll-seconds") == "7"
        listing = poller.xpath(".//*[@id='conversation-list']")[0]
        assert listing.get("x-ref") == "target"
        assert listing.get("hx-get") == reverse("conversations:inbox_poll")
        assert "conversationChanged from:body" in listing.get("hx-trigger")
        assert listing.get("hx-target") == "this"
        assert listing.get("hx-swap") == "outerHTML"
        assert tree.xpath("//input[@id='inbox-since']")[0].get("value") == since
        assert tree.xpath("//input[@id='inbox-since']")[0].get("name") == "since"

    def test_nothing_changed_is_204_and_writes_nothing(
        self, seen, logged_in_client
    ) -> None:
        user, _, conversation, since = seen
        before = Conversation.objects.get(pk=conversation.pk).last_message_at

        response = logged_in_client(user).get(inbox_poll_url(since=since), **HTMX)

        assert response.status_code == 204
        assert Conversation.objects.get(pk=conversation.pk).last_message_at == before

    def test_a_new_message_rerenders_the_list_with_its_row_first(
        self, seen, logged_in_client
    ) -> None:
        user, other, _, since = seen
        third = UserFactory(first_name="Newest", last_name="Sender")
        MessageFactory(conversation=ConversationFactory(between=(user, third)))

        response = logged_in_client(user).get(inbox_poll_url(since=since), **HTMX)

        assert response.status_code == 200
        content = response.content.decode()
        assert content.index("Newest Sender") < content.index(other.display_name)
        assert "<html" not in content
        marker = poll_tree(response).xpath("//input[@id='inbox-since']")[0]
        assert marker.get("hx-swap-oob") == "outerHTML"
        assert marker.get("value") != since

    @pytest.mark.parametrize("since", ["", "not-a-date", "2026-01-01T00:00:00"])
    def test_a_missing_or_malformed_marker_rerenders(
        self, seen, logged_in_client, since
    ) -> None:
        user, *_ = seen

        response = logged_in_client(user).get(inbox_poll_url(since=since), **HTMX)

        assert response.status_code == 200
        assert 'id="conversation-list"' in response.content.decode()

    def test_the_open_threads_row_keeps_aria_current(
        self, seen, logged_in_client
    ) -> None:
        user, _, conversation, _ = seen

        response = logged_in_client(user).get(
            inbox_poll_url(current=str(conversation.pk)), **HTMX
        )

        links = poll_tree(response).xpath("//a[@aria-current='page']")
        assert [link.get("href") for link in links] == [thread_url(conversation)]

    def test_the_thread_page_tells_the_poll_which_thread_is_open(
        self, seen, logged_in_client
    ) -> None:
        user, _, conversation, _ = seen

        tree = html.fromstring(
            logged_in_client(user).get(thread_url(conversation)).content
        )

        current = tree.xpath("//input[@id='inbox-current']")[0]
        assert current.get("name") == "current"
        assert current.get("value") == str(conversation.pk)
        listing = tree.xpath("//*[@id='conversation-list']")[0]
        assert "#inbox-current" in listing.get("hx-include")

    def test_another_users_conversation_is_not_listed(
        self, seen, logged_in_client
    ) -> None:
        user, *_ = seen
        a, b = UserFactory(), UserFactory()
        MessageFactory(
            conversation=ConversationFactory(between=(a, b)), body="Not for you"
        )

        response = logged_in_client(user).get(inbox_poll_url(), **HTMX)

        assert a.display_name not in response.content.decode()
