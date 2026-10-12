"""The thread page and the send endpoint."""

from __future__ import annotations

import uuid

import pytest
from lxml import html

from django.conf import settings as django_settings
from django.urls import reverse

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.comms.factories import ConversationFactory, MessageFactory
from freedom_ls.comms.messaging import inbox_for, mark_conversation_read
from freedom_ls.comms.messaging_policy import (
    MessagingDecision,
    MessagingPolicy,
    MessagingRefusal,
)
from freedom_ls.comms.models import ConversationParticipant, Message
from freedom_ls.site_aware_models.models import _thread_locals


class AllowPolicy(MessagingPolicy):
    def can_start(self, *, sender, recipient, site):
        return MessagingDecision.allow()

    def can_reply(self, *, sender, recipient, site, conversation):
        return MessagingDecision.allow()


class ClosedPolicy(MessagingPolicy):
    def can_start(self, *, sender, recipient, site):
        return MessagingDecision.refuse(MessagingRefusal.CLOSED_BY_CONFIGURATION)

    def can_reply(self, *, sender, recipient, site, conversation):
        return MessagingDecision.refuse(MessagingRefusal.CLOSED_BY_CONFIGURATION)


@pytest.fixture
def allow_policy(settings) -> None:
    settings.MESSAGING_POLICY = f"{__name__}.AllowPolicy"


@pytest.fixture
def closed_policy(settings) -> None:
    settings.MESSAGING_POLICY = f"{__name__}.ClosedPolicy"


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

    def test_the_composer_posts_once_per_click(self, pair, logged_in_client) -> None:
        user, _, conversation = pair

        response = logged_in_client(user).get(thread_url(conversation))

        tree = html.fromstring(response.content)
        composer = tree.get_element_by_id("composer")
        button = composer.xpath(".//button[@type='submit']")[0]
        assert composer.get("hx-sync") == "this:drop"
        assert button.get("hx-disabled-elt") == "this"
        assert button.get("aria-label") == "Send"

    def test_the_composer_is_labelled_with_the_name(
        self, pair, logged_in_client
    ) -> None:
        user, other, conversation = pair
        other.first_name = "Kai"
        other.save()

        response = logged_in_client(user).get(thread_url(conversation))

        label = html.fromstring(response.content).xpath("//label[@for='message-body']")
        assert label[0].text_content().strip() == "Message to Kai"

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
        self, mock_site_context, logged_in_client
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
