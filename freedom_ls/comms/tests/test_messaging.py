"""The messaging service: pairing, sending, idempotency and read state."""

from __future__ import annotations

import threading
import uuid
from datetime import timedelta
from typing import cast

import pytest

from django.db import connection
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.comms.factories import (
    ConversationFactory,
    MessageFactory,
    NotificationFactory,
)
from freedom_ls.comms.messaging import (
    BLANK_BODY,
    TOO_LONG_BODY,
    SendResult,
    closed_note_copy,
    conversation_between,
    decode_cursor,
    encode_cursor,
    get_or_create_conversation,
    inbox_for,
    latest_messages,
    latest_page,
    mark_conversation_read,
    messages_after,
    new_messages_announcement,
    other_participant,
    page_before,
    pair_key_for,
    refusal_alert_copy,
    render_message_entries,
    reply_decision,
    reply_decisions,
    search_recipients,
    send_message,
    unread_conversation_count,
)
from freedom_ls.comms.messaging_policy import (
    MessagingDecision,
    MessagingPolicy,
    MessagingRefusal,
)
from freedom_ls.comms.models import (
    Conversation,
    ConversationParticipant,
    Message,
    Notification,
)
from freedom_ls.site_aware_models.factories import SiteFactory
from freedom_ls.site_aware_models.models import _thread_locals


class AllowPolicy(MessagingPolicy):
    def can_start(self, *, sender, recipient, site):
        return MessagingDecision.allow()

    def can_reply(self, *, sender, recipient, site, conversation):
        return MessagingDecision.allow()


class NoneOfThemPolicy(MessagingPolicy):
    def recipients_for(self, *, sender, site):
        return User.objects.none()


class ClosedPolicy(MessagingPolicy):
    def can_start(self, *, sender, recipient, site):
        return MessagingDecision.refuse(MessagingRefusal.CLOSED_BY_CONFIGURATION)

    def can_reply(self, *, sender, recipient, site, conversation):
        return MessagingDecision.refuse(MessagingRefusal.CLOSED_BY_CONFIGURATION)


def stored(result: SendResult) -> Message:
    assert result.message is not None
    return result.message


def stored_conversation(result: SendResult) -> Conversation:
    assert result.conversation is not None
    return result.conversation


@pytest.fixture
def allow_policy(settings) -> None:
    settings.MESSAGING_POLICY = f"{__name__}.AllowPolicy"


@pytest.fixture
def closed_policy(settings) -> None:
    settings.MESSAGING_POLICY = f"{__name__}.ClosedPolicy"


@pytest.fixture(autouse=True)
def _length_limit(settings) -> None:
    settings.MESSAGE_MAX_LENGTH = 2000


@pytest.mark.django_db
class TestPairing:
    def test_pair_key_is_the_same_in_both_orders(self, mock_site_context) -> None:
        user_a = UserFactory()
        user_b = UserFactory()

        assert pair_key_for(user_a, user_b) == pair_key_for(user_b, user_a)

    def test_pair_key_lists_the_lower_pk_first(self, mock_site_context) -> None:
        user_a = UserFactory()
        user_b = UserFactory()

        assert pair_key_for(user_b, user_a) == f"{user_a.pk}:{user_b.pk}"

    def test_get_or_create_returns_one_conversation_in_both_orders(
        self, mock_site_context, site
    ) -> None:
        user_a = UserFactory()
        user_b = UserFactory()

        first = get_or_create_conversation(user_a=user_a, user_b=user_b, site=site)
        second = get_or_create_conversation(user_a=user_b, user_b=user_a, site=site)

        assert first.pk == second.pk

    def test_get_or_create_adds_both_participants(
        self, mock_site_context, site
    ) -> None:
        user_a = UserFactory()
        user_b = UserFactory()

        conversation = get_or_create_conversation(
            user_a=user_a, user_b=user_b, site=site
        )

        assert set(
            ConversationParticipant.objects.filter(
                conversation=conversation
            ).values_list("user_id", flat=True)
        ) == {user_a.pk, user_b.pk}

    def test_the_same_pair_on_another_site_gets_its_own_conversation(
        self, mock_site_context, site
    ) -> None:
        other_site = SiteFactory()
        user_a = UserFactory()
        user_b = UserFactory()

        here = get_or_create_conversation(user_a=user_a, user_b=user_b, site=site)
        there = get_or_create_conversation(
            user_a=user_a, user_b=user_b, site=other_site
        )

        assert here.pk != there.pk

    def test_conversation_between_is_none_for_a_stranger_pair(
        self, mock_site_context, site
    ) -> None:
        assert conversation_between(UserFactory(), UserFactory(), site) is None

    @pytest.mark.usefixtures("allow_policy")
    def test_rows_created_with_no_request_carry_the_site(
        self, mock_site_context, site
    ) -> None:
        user_a = UserFactory()
        user_b = UserFactory()
        saved_request = _thread_locals.request
        del _thread_locals.request
        try:
            conversation = get_or_create_conversation(
                user_a=user_a, user_b=user_b, site=site
            )
            result = send_message(
                sender=user_a,
                recipient=user_b,
                body="Hello",
                client_key=uuid.uuid4(),
                site=site,
                conversation=conversation,
            )
        finally:
            _thread_locals.request = saved_request

        sites = {
            conversation.site_id,
            *ConversationParticipant.objects.filter(
                conversation=conversation
            ).values_list("site_id", flat=True),
            stored(result).site_id,
        }
        assert sites == {site.pk}


@pytest.mark.django_db(transaction=True)
def test_concurrent_first_messages_create_one_conversation(site) -> None:
    user_a = UserFactory(site=site)
    user_b = UserFactory(site=site)
    barrier = threading.Barrier(2)
    pks: list[uuid.UUID] = []

    def create() -> None:
        try:
            barrier.wait()
            pks.append(
                get_or_create_conversation(user_a=user_a, user_b=user_b, site=site).pk
            )
        finally:
            connection.close()

    threads = [threading.Thread(target=create) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(pks) == 2
    assert len(set(pks)) == 1
    assert Conversation._base_manager.filter(site=site).count() == 1


@pytest.mark.django_db
@pytest.mark.usefixtures("allow_policy")
class TestSendMessage:
    def test_sending_on_a_conversation_stores_the_message(
        self, mock_site_context, site
    ) -> None:
        sender, recipient = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(sender, recipient))

        result = send_message(
            sender=sender,
            body="Hi there",
            client_key=uuid.uuid4(),
            site=site,
            conversation=conversation,
        )

        assert stored(result).body == "Hi there"
        assert stored(result).sender == sender

    def test_sending_to_a_recipient_starts_the_conversation(
        self, mock_site_context, site
    ) -> None:
        sender, recipient = UserFactory(), UserFactory()

        result = send_message(
            sender=sender,
            recipient=recipient,
            body="Hi",
            client_key=uuid.uuid4(),
            site=site,
        )

        assert stored_conversation(result).pair_key == pair_key_for(sender, recipient)

    def test_sending_sets_last_message_at_and_the_senders_last_read_at(
        self, mock_site_context, site
    ) -> None:
        sender, recipient = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(sender, recipient))

        result = send_message(
            sender=sender,
            body="Hi",
            client_key=uuid.uuid4(),
            site=site,
            conversation=conversation,
        )

        conversation.refresh_from_db()
        participant = ConversationParticipant.objects.get(
            conversation=conversation, user=sender
        )
        assert conversation.last_message_at == stored(result).created_at
        assert participant.last_read_at == stored(result).created_at

    def test_an_unread_incoming_message_keeps_the_senders_marker_where_it_was(
        self, mock_site_context, site
    ) -> None:
        sender, recipient = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(sender, recipient))
        MessageFactory(conversation=conversation, sender=recipient)

        send_message(
            sender=sender,
            body="Hi",
            client_key=uuid.uuid4(),
            site=site,
            conversation=conversation,
        )

        assert (
            ConversationParticipant.objects.get(
                conversation=conversation, user=sender
            ).last_read_at
            is None
        )

    def test_the_recipients_last_read_at_is_untouched(
        self, mock_site_context, site
    ) -> None:
        sender, recipient = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(sender, recipient))

        send_message(
            sender=sender,
            body="Hi",
            client_key=uuid.uuid4(),
            site=site,
            conversation=conversation,
        )

        assert (
            ConversationParticipant.objects.get(
                conversation=conversation, user=recipient
            ).last_read_at
            is None
        )

    def test_a_repeated_client_key_returns_the_original(
        self, mock_site_context, site
    ) -> None:
        sender, recipient = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(sender, recipient))
        key = uuid.uuid4()
        first = send_message(
            sender=sender,
            body="Hi",
            client_key=key,
            site=site,
            conversation=conversation,
        )

        second = send_message(
            sender=sender,
            body="Hi",
            client_key=key,
            site=site,
            conversation=conversation,
        )

        assert stored(second).pk == stored(first).pk
        assert Message.objects.filter(conversation=conversation).count() == 1

    def test_the_same_key_from_the_other_participant_is_a_new_message(
        self, mock_site_context, site
    ) -> None:
        sender, recipient = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(sender, recipient))
        key = uuid.uuid4()
        send_message(
            sender=sender,
            body="Hi",
            client_key=key,
            site=site,
            conversation=conversation,
        )

        send_message(
            sender=recipient,
            body="Hi back",
            client_key=key,
            site=site,
            conversation=conversation,
        )

        assert Message.objects.filter(conversation=conversation).count() == 2

    @pytest.mark.parametrize("body", ["", "   ", "\n\n"])
    def test_a_blank_body_is_refused(self, mock_site_context, site, body) -> None:
        sender, recipient = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(sender, recipient))

        result = send_message(
            sender=sender,
            body=body,
            client_key=uuid.uuid4(),
            site=site,
            conversation=conversation,
        )

        assert result.body_error == BLANK_BODY
        assert Message.objects.count() == 0

    def test_a_body_over_the_limit_is_refused(self, mock_site_context, site) -> None:
        sender, recipient = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(sender, recipient))

        result = send_message(
            sender=sender,
            body="a" * 2001,
            client_key=uuid.uuid4(),
            site=site,
            conversation=conversation,
        )

        assert result.body_error == TOO_LONG_BODY % {"limit": 2000}
        assert Message.objects.count() == 0

    def test_a_body_at_the_limit_is_accepted(self, mock_site_context, site) -> None:
        sender, recipient = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(sender, recipient))

        result = send_message(
            sender=sender,
            body="a" * 2000,
            client_key=uuid.uuid4(),
            site=site,
            conversation=conversation,
        )

        assert result.message is not None

    def test_windows_line_endings_are_normalised(self, mock_site_context, site) -> None:
        sender, recipient = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(sender, recipient))

        result = send_message(
            sender=sender,
            body="one\r\ntwo",
            client_key=uuid.uuid4(),
            site=site,
            conversation=conversation,
        )

        assert stored(result).body == "one\ntwo"


@pytest.mark.django_db
@pytest.mark.usefixtures("closed_policy")
class TestSendRefused:
    def test_a_refused_start_stores_nothing(self, mock_site_context, site) -> None:
        sender, recipient = UserFactory(), UserFactory()

        result = send_message(
            sender=sender,
            recipient=recipient,
            body="Hi",
            client_key=uuid.uuid4(),
            site=site,
        )

        assert result.refusal == MessagingRefusal.CLOSED_BY_CONFIGURATION
        assert Conversation.objects.count() == 0
        assert Message.objects.count() == 0

    def test_a_refused_reply_stores_nothing(self, mock_site_context, site) -> None:
        sender, recipient = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(sender, recipient))

        result = send_message(
            sender=sender,
            body="Hi",
            client_key=uuid.uuid4(),
            site=site,
            conversation=conversation,
        )

        assert result.refusal == MessagingRefusal.CLOSED_BY_CONFIGURATION
        assert Message.objects.count() == 0

    def test_a_repeat_after_the_policy_closed_returns_the_original_on_the_conversation(
        self, mock_site_context, site
    ) -> None:
        sender, recipient = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(sender, recipient))
        key = uuid.uuid4()
        original = MessageFactory(
            conversation=conversation, sender=sender, client_key=key
        )

        result = send_message(
            sender=sender,
            body="Hi",
            client_key=key,
            site=site,
            conversation=conversation,
        )

        assert stored(result).pk == original.pk
        assert result.refusal is None

    def test_a_repeat_after_the_policy_closed_returns_the_original_on_the_recipient_path(
        self, mock_site_context, site
    ) -> None:
        sender, recipient = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(sender, recipient))
        key = uuid.uuid4()
        original = MessageFactory(
            conversation=conversation, sender=sender, client_key=key
        )

        result = send_message(
            sender=sender,
            recipient=recipient,
            body="Hi",
            client_key=key,
            site=site,
        )

        assert stored(result).pk == original.pk


@pytest.mark.django_db
class TestReadState:
    def test_mark_read_sets_last_read_at(self, mock_site_context) -> None:
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        moment = timezone.now()

        mark_conversation_read(user=user, conversation=conversation, up_to=moment)

        assert (
            ConversationParticipant.objects.get(
                conversation=conversation, user=user
            ).last_read_at
            == moment
        )

    def test_mark_read_never_moves_last_read_at_backwards(
        self, mock_site_context
    ) -> None:
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        later = timezone.now()
        mark_conversation_read(user=user, conversation=conversation, up_to=later)

        mark_conversation_read(
            user=user, conversation=conversation, up_to=later - timedelta(hours=1)
        )

        assert (
            ConversationParticipant.objects.get(
                conversation=conversation, user=user
            ).last_read_at
            == later
        )

    def test_mark_read_says_whether_the_marker_moved(self, mock_site_context) -> None:
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        moment = timezone.now()

        first = mark_conversation_read(
            user=user, conversation=conversation, up_to=moment
        )
        again = mark_conversation_read(
            user=user, conversation=conversation, up_to=moment
        )

        assert first is True
        assert again is False


@pytest.mark.django_db
class TestConversationQueries:
    def test_other_participant_is_the_other_user(self, mock_site_context) -> None:
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))

        assert other_participant(conversation, user) == other

    def test_other_participant_is_none_once_the_other_account_is_deleted(
        self, mock_site_context
    ) -> None:
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        other.delete()

        assert other_participant(conversation, user) is None

    def test_reply_decision_refuses_inactive_user_without_asking_the_policy(
        self, mock_site_context, settings
    ) -> None:
        settings.MESSAGING_POLICY = f"{__name__}.MessagingPolicy"
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        other.delete()

        decision = reply_decision(viewer=user, conversation=conversation)

        assert decision.reason == MessagingRefusal.INACTIVE_USER

    def test_reply_decisions_refuses_inactive_user_without_asking_the_policy(
        self, mock_site_context, settings
    ) -> None:
        settings.MESSAGING_POLICY = f"{__name__}.MessagingPolicy"
        user, other = UserFactory(), UserFactory()
        conversation = cast("Conversation", ConversationFactory(between=(user, other)))
        other.delete()

        decisions = reply_decisions(viewer=user, conversations=[conversation])

        assert decisions[conversation.pk].reason == MessagingRefusal.INACTIVE_USER

    def test_reply_decisions_asks_the_policy_about_the_remaining_conversations(
        self, mock_site_context, closed_policy
    ) -> None:
        user, gone, kept = UserFactory(), UserFactory(), UserFactory()
        with_gone = cast("Conversation", ConversationFactory(between=(user, gone)))
        with_kept = cast("Conversation", ConversationFactory(between=(user, kept)))
        gone.delete()

        decisions = reply_decisions(viewer=user, conversations=[with_gone, with_kept])

        assert (decisions[with_gone.pk].reason, decisions[with_kept.pk].reason) == (
            MessagingRefusal.INACTIVE_USER,
            MessagingRefusal.CLOSED_BY_CONFIGURATION,
        )

    def test_a_policy_that_only_defines_can_reply_answers_in_bulk(
        self, mock_site_context, allow_policy
    ) -> None:
        user = UserFactory()
        conversation = cast(
            "Conversation", ConversationFactory(between=(user, UserFactory()))
        )

        decisions = reply_decisions(viewer=user, conversations=[conversation])

        assert decisions[conversation.pk].allowed is True

    def test_latest_messages_are_the_newest_few_oldest_first(
        self, mock_site_context
    ) -> None:
        conversation = ConversationFactory(between=(UserFactory(), UserFactory()))
        messages = [MessageFactory(conversation=conversation) for _ in range(4)]

        assert [m.pk for m in latest_messages(conversation, 3)] == [
            m.pk for m in messages[1:]
        ]

    def test_latest_page_reads_oldest_to_newest(self, mock_site_context) -> None:
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        first = MessageFactory(conversation=conversation)
        second = MessageFactory(conversation=conversation)

        assert [m.pk for m in latest_page(conversation)[0]] == [first.pk, second.pk]

    def test_latest_page_holds_only_the_newest_page_size(
        self, mock_site_context, settings
    ) -> None:
        settings.MESSAGE_PAGE_SIZE = 2
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        MessageFactory(conversation=conversation)
        second = MessageFactory(conversation=conversation)
        third = MessageFactory(conversation=conversation)

        assert [m.pk for m in latest_page(conversation)[0]] == [second.pk, third.pk]


@pytest.mark.django_db
class TestRefusalAlertCopy:
    def test_names_the_other_participant(self, mock_site_context) -> None:
        other = UserFactory(first_name="Kai")

        copy = refusal_alert_copy(MessagingRefusal.CLOSED_BY_CONFIGURATION, other)

        assert copy == (
            "Not sent. Kai can't receive messages from you here. "
            "Your text is still in the box."
        )

    def test_without_another_participant_it_is_generic(self) -> None:
        copy = refusal_alert_copy(MessagingRefusal.INACTIVE_USER, None)

        assert copy == (
            "Not sent. This conversation can't take new messages. "
            "Your text is still in the box."
        )


@pytest.mark.django_db
class TestInboxFor:
    def test_each_viewer_gets_their_own_read_marker(self, mock_site_context) -> None:
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        message = MessageFactory(conversation=conversation, sender=other)
        mark_conversation_read(
            user=user, conversation=conversation, up_to=message.created_at
        )

        mine = inbox_for(user).get(pk=conversation.pk)
        theirs = inbox_for(other).get(pk=conversation.pk)

        assert mine.viewer_last_read_at == message.created_at
        assert mine.is_unread is False
        assert theirs.viewer_last_read_at is None
        assert theirs.is_unread is True

    def test_only_the_viewers_conversations_are_listed(self, mock_site_context) -> None:
        user, other, stranger = UserFactory(), UserFactory(), UserFactory()
        mine = ConversationFactory(between=(user, other))
        ConversationFactory(between=(other, stranger))

        assert list(inbox_for(user)) == [mine]

    def test_newest_activity_comes_first_and_empty_conversations_last(
        self, mock_site_context
    ) -> None:
        user = UserFactory()
        empty = ConversationFactory(between=(user, UserFactory()))
        older = ConversationFactory(between=(user, UserFactory()))
        newer = ConversationFactory(between=(user, UserFactory()))
        MessageFactory(conversation=older)
        MessageFactory(conversation=newer)

        assert list(inbox_for(user)) == [newer, older, empty]

    def test_a_conversation_with_no_messages_is_not_unread(
        self, mock_site_context
    ) -> None:
        user = UserFactory()
        conversation = ConversationFactory(between=(user, UserFactory()))

        assert inbox_for(user).get(pk=conversation.pk).is_unread is False

    def test_other_participants_are_prefetched(
        self, mock_site_context, django_assert_num_queries
    ) -> None:
        user, other = UserFactory(), UserFactory()
        ConversationFactory(between=(user, other))
        conversations = list(inbox_for(user))

        with django_assert_num_queries(0):
            assert other_participant(conversations[0], user) == other

    def test_a_message_created_after_the_mark_stays_unread(
        self, mock_site_context
    ) -> None:
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        shown = MessageFactory(conversation=conversation, sender=other)
        mark_conversation_read(
            user=user, conversation=conversation, up_to=shown.created_at
        )

        MessageFactory(conversation=conversation, sender=other)

        assert inbox_for(user).get(pk=conversation.pk).is_unread is True


@pytest.mark.django_db
class TestUnreadConversationCount:
    def test_it_counts_conversations_not_messages(self, mock_site_context) -> None:
        user = UserFactory()
        busy = ConversationFactory(between=(user, UserFactory()))
        for _ in range(3):
            MessageFactory(conversation=busy)
        quiet = ConversationFactory(between=(user, UserFactory()))
        MessageFactory(conversation=quiet)
        ConversationFactory(between=(user, UserFactory()))

        assert unread_conversation_count(user) == 2

    def test_it_runs_one_query(
        self, mock_site_context, django_assert_num_queries
    ) -> None:
        user = UserFactory()
        MessageFactory(conversation=ConversationFactory(between=(user, UserFactory())))

        with django_assert_num_queries(1):
            unread_conversation_count(user)


@pytest.mark.django_db
class TestSearchRecipients:
    @pytest.fixture
    def sender(self, mock_site_context):
        return UserFactory()

    def search(self, sender, site, term, candidates, include_email=False):
        return search_recipients(
            sender=sender,
            site=site,
            term=term,
            candidates=candidates,
            include_email=include_email,
        )

    def names(self, result) -> list[str]:
        return [user.display_name for g in result.groups for user in g.users]

    def test_it_lists_everyone_without_a_term_at_fifteen_or_fewer(
        self, sender, mock_site_context
    ) -> None:
        UserFactory.create_batch(15)

        result = self.search(
            sender, mock_site_context, "", User.objects.exclude(pk=sender.pk)
        )

        assert not result.needs_term
        assert result.count == 15

    def test_it_asks_for_a_term_above_fifteen_candidates(
        self, sender, mock_site_context
    ) -> None:
        UserFactory.create_batch(16)

        result = self.search(
            sender, mock_site_context, "", User.objects.exclude(pk=sender.pk)
        )

        assert result.needs_term
        assert result.groups == []

    def test_a_one_character_term_needs_more(self, sender, mock_site_context) -> None:
        UserFactory(first_name="Kai")

        result = self.search(
            sender, mock_site_context, "k", User.objects.exclude(pk=sender.pk)
        )

        assert result.needs_term

    def test_it_matches_first_or_last_name_ignoring_case(
        self, sender, mock_site_context
    ) -> None:
        UserFactory(first_name="Kai", last_name="Ngata")
        UserFactory(first_name="Ana", last_name="Kaiser")
        UserFactory(first_name="Zed", last_name="Other")

        result = self.search(
            sender, mock_site_context, "KAI", User.objects.exclude(pk=sender.pk)
        )

        assert self.names(result) == ["Ana Kaiser", "Kai Ngata"]

    def test_a_full_name_matches_across_first_and_last_name(
        self, sender, mock_site_context
    ) -> None:
        UserFactory(first_name="Jane", last_name="Smith")
        UserFactory(first_name="Jane", last_name="Doe")

        result = self.search(
            sender, mock_site_context, "jane  smith", User.objects.exclude(pk=sender.pk)
        )

        assert self.names(result) == ["Jane Smith"]

    def test_it_caps_at_twenty_and_flags_truncation(
        self, sender, mock_site_context
    ) -> None:
        UserFactory.create_batch(21, first_name="Match")

        result = self.search(
            sender, mock_site_context, "match", User.objects.exclude(pk=sender.pk)
        )

        assert result.count == 20
        assert result.truncated

    def test_twenty_matches_are_not_truncated(self, sender, mock_site_context) -> None:
        UserFactory.create_batch(20, first_name="Match")

        result = self.search(
            sender, mock_site_context, "match", User.objects.exclude(pk=sender.pk)
        )

        assert result.count == 20
        assert not result.truncated

    def test_email_matches_only_when_asked(self, sender, mock_site_context) -> None:
        UserFactory(first_name="Kai", email="zzunique@example.com")
        candidates = User.objects.exclude(pk=sender.pk)

        without = self.search(sender, mock_site_context, "zzunique", candidates)
        with_email = self.search(
            sender, mock_site_context, "zzunique", candidates, include_email=True
        )

        assert without.count == 0
        assert with_email.count == 1

    def test_it_never_returns_a_user_outside_the_candidates(
        self, sender, mock_site_context
    ) -> None:
        UserFactory(first_name="Kai", last_name="Allowed")
        refused = UserFactory(first_name="Kai", last_name="Refused")

        result = self.search(
            sender,
            mock_site_context,
            "kai",
            User.objects.exclude(pk__in=[sender.pk, refused.pk]),
        )

        assert self.names(result) == ["Kai Allowed"]

    def test_a_refused_name_looks_the_same_as_an_absent_one(
        self, sender, mock_site_context
    ) -> None:
        UserFactory(first_name="Ghost", last_name="Refused")
        candidates = User.objects.none()

        refused = self.search(sender, mock_site_context, "ghost", candidates)
        absent = self.search(sender, mock_site_context, "nobodyhere", candidates)

        assert refused == absent

    def test_it_defaults_candidates_to_the_policys_recipients(
        self, sender, mock_site_context, settings
    ) -> None:
        settings.MESSAGING_POLICY = f"{__name__}.NoneOfThemPolicy"
        UserFactory(first_name="Kai")

        result = search_recipients(
            sender=sender, site=mock_site_context, term="kai", include_email=False
        )

        assert result.count == 0


@pytest.mark.django_db
class TestClosedNoteCopy:
    def test_the_heading_is_the_same_for_every_reason(self) -> None:
        headings = {closed_note_copy(reason, None)[0] for reason in MessagingRefusal}

        assert headings == {"Replies are closed"}

    def test_closed_by_configuration_names_the_other_participant(
        self, mock_site_context
    ) -> None:
        other = UserFactory(first_name="Kai")

        _, body = closed_note_copy(MessagingRefusal.CLOSED_BY_CONFIGURATION, other)

        assert body == (
            "Messaging between you and Kai is closed here. "
            "You can both still read this conversation."
        )

    def test_no_relationship_names_the_other_participant(
        self, mock_site_context
    ) -> None:
        other = UserFactory(first_name="Kai")

        _, body = closed_note_copy(MessagingRefusal.NO_RELATIONSHIP, other)

        assert body == (
            "You can no longer message Kai from here. "
            "You can both still read this conversation."
        )

    def test_a_blank_first_name_falls_back_to_the_display_name(
        self, mock_site_context
    ) -> None:
        other = UserFactory(first_name="")

        _, body = closed_note_copy(MessagingRefusal.NO_RELATIONSHIP, other)

        assert other.display_name in body

    @pytest.mark.parametrize(
        "reason", [MessagingRefusal.INACTIVE_USER, MessagingRefusal.SAME_USER]
    )
    def test_inactive_and_same_user_share_the_generic_body(
        self, reason: MessagingRefusal
    ) -> None:
        _, body = closed_note_copy(reason, None)

        assert (
            body == "This conversation can't take new messages. You can still read it."
        )


@pytest.mark.django_db
class TestDeletedParticipant:
    def test_deleting_a_user_keeps_the_conversation_and_nulls_the_sender(
        self, mock_site_context
    ) -> None:
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        MessageFactory(conversation=conversation, sender=other)
        MessageFactory(conversation=conversation, sender=user)
        other.delete()

        assert Conversation.objects.filter(pk=conversation.pk).exists()
        assert Message.objects.filter(conversation=conversation).count() == 2
        assert (
            Message.objects.filter(
                conversation=conversation, sender__isnull=True
            ).count()
            == 1
        )

    def test_a_send_into_the_conversation_stores_nothing(
        self, mock_site_context, site
    ) -> None:
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        other.delete()

        result = send_message(
            sender=user,
            body="Hello?",
            client_key=uuid.uuid4(),
            site=site,
            conversation=conversation,
        )

        assert result.refusal == MessagingRefusal.INACTIVE_USER
        assert Message.objects.count() == 0


def _stamped(conversation, sender, at, body="x") -> Message:
    message = MessageFactory(conversation=conversation, sender=sender, body=body)
    Message.objects.filter(pk=message.pk).update(created_at=at)
    return cast("Message", Message.objects.get(pk=message.pk))


@pytest.mark.django_db
class TestCursor:
    def test_a_cursor_round_trips(self, mock_site_context) -> None:
        user, other = UserFactory(), UserFactory()
        message = MessageFactory(
            conversation=ConversationFactory(between=(user, other))
        )

        assert decode_cursor(encode_cursor(message)) == (
            message.created_at,
            message.pk,
        )

    @pytest.mark.parametrize(
        "value",
        ["", "garbage", "not-a-date~not-a-uuid", "2026-01-01T00:00:00+00:00~nope"],
    )
    def test_a_malformed_cursor_is_none(self, value) -> None:
        assert decode_cursor(value) is None


@pytest.mark.django_db
class TestPageBefore:
    @pytest.fixture
    def thread(self, mock_site_context, settings):
        settings.MESSAGE_PAGE_SIZE = 3
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        base = timezone.now() - timedelta(days=1)
        messages = [
            _stamped(conversation, user, base + timedelta(minutes=i)) for i in range(7)
        ]
        return conversation, messages

    def test_the_latest_page_says_older_messages_remain(self, thread) -> None:
        conversation, messages = thread

        page, has_more = latest_page(conversation)

        assert [m.pk for m in page] == [m.pk for m in messages[4:]]
        assert has_more is True

    def test_a_page_before_a_cursor_holds_the_page_size_oldest_first(
        self, thread
    ) -> None:
        conversation, messages = thread

        page, has_more = page_before(
            conversation, decode_cursor(encode_cursor(messages[4]))
        )

        assert [m.pk for m in page] == [m.pk for m in messages[1:4]]
        assert has_more is True

    def test_an_exactly_full_last_page_has_nothing_more(self, thread) -> None:
        conversation, messages = thread

        page, has_more = page_before(
            conversation, decode_cursor(encode_cursor(messages[3]))
        )

        assert [m.pk for m in page] == [m.pk for m in messages[0:3]]
        assert has_more is False

    def test_messages_sharing_a_timestamp_are_neither_skipped_nor_repeated(
        self, mock_site_context, settings
    ) -> None:
        settings.MESSAGE_PAGE_SIZE = 2
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        at = timezone.now() - timedelta(hours=1)
        same = sorted(
            (_stamped(conversation, user, at) for _ in range(5)),
            key=lambda m: m.pk,
        )

        first, _ = page_before(conversation, (at, same[4].pk))
        second, _ = page_before(conversation, (at, first[0].pk))

        assert {m.pk for m in first}.isdisjoint({m.pk for m in second})
        assert [m.pk for m in first] == [m.pk for m in same[2:4]]
        assert [m.pk for m in second] == [m.pk for m in same[0:2]]

    def test_a_message_landing_after_the_cursor_is_not_in_the_page(
        self, thread
    ) -> None:
        conversation, messages = thread
        cursor = decode_cursor(encode_cursor(messages[4]))
        newer = MessageFactory(conversation=conversation)

        page, _ = page_before(conversation, cursor)

        assert newer.pk not in {m.pk for m in page}


@pytest.mark.django_db
class TestMessagesAfter:
    @pytest.fixture
    def thread(self, mock_site_context):
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        base = timezone.now() - timedelta(days=1)
        messages = [
            _stamped(conversation, other, base + timedelta(minutes=i)) for i in range(5)
        ]
        return conversation, messages

    def test_it_returns_the_messages_after_the_cursor_oldest_first(
        self, thread
    ) -> None:
        conversation, messages = thread

        found = messages_after(conversation, decode_cursor(encode_cursor(messages[1])))

        assert [m.pk for m in found] == [m.pk for m in messages[2:]]

    def test_it_returns_nothing_at_the_newest_message(self, thread) -> None:
        conversation, messages = thread

        assert (
            messages_after(conversation, decode_cursor(encode_cursor(messages[-1])))
            == []
        )

    def test_no_cursor_means_the_whole_thread(self, thread) -> None:
        conversation, messages = thread

        assert [m.pk for m in messages_after(conversation, None)] == [
            m.pk for m in messages
        ]

    def test_messages_sharing_the_cursor_timestamp_are_split_by_id(
        self, mock_site_context
    ) -> None:
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        at = timezone.now() - timedelta(hours=1)
        same = sorted(
            (_stamped(conversation, other, at) for _ in range(4)), key=lambda m: m.pk
        )

        found = messages_after(conversation, (at, same[1].pk))

        assert [m.pk for m in found] == [m.pk for m in same[2:]]


class TestNewMessagesAnnouncement:
    def test_one_message_is_singular(self) -> None:
        assert new_messages_announcement(1, "Kai") == "1 new message from Kai"

    def test_several_messages_are_plural(self) -> None:
        assert new_messages_announcement(3, "Kai") == "3 new messages from Kai"


@pytest.mark.django_db
class TestRenderMessageEntries:
    def test_the_first_message_of_a_thread_shows_day_and_sender(
        self, mock_site_context
    ) -> None:
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        message = _stamped(conversation, user, timezone.now())

        (entry,) = render_message_entries([message], None)

        assert (entry.show_day, entry.show_sender) == (True, True)

    def test_a_same_day_same_sender_follow_up_shows_neither(
        self, mock_site_context
    ) -> None:
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        at = timezone.now().replace(hour=12, minute=0)
        first = _stamped(conversation, user, at)
        second = _stamped(conversation, user, at + timedelta(minutes=1))

        entries = render_message_entries([second], first)

        assert (entries[0].show_day, entries[0].show_sender) == (False, False)

    def test_a_new_sender_on_the_same_day_shows_only_the_sender(
        self, mock_site_context
    ) -> None:
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        at = timezone.now().replace(hour=12, minute=0)
        first = _stamped(conversation, user, at)
        second = _stamped(conversation, other, at + timedelta(minutes=1))

        entries = render_message_entries([second], first)

        assert (entries[0].show_day, entries[0].show_sender) == (False, True)

    def test_a_new_local_day_shows_day_and_sender_even_for_the_same_sender(
        self, mock_site_context
    ) -> None:
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        first = _stamped(conversation, user, timezone.now() - timedelta(days=2))
        second = _stamped(conversation, user, timezone.now() - timedelta(days=1))

        entries = render_message_entries([first, second], None)

        assert [(e.show_day, e.show_sender) for e in entries] == [
            (True, True),
            (True, True),
        ]


def _message_notifications(user, conversation):
    return Notification.objects.filter(
        user=user, category="message.received", object_id=str(conversation.pk)
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("allow_policy")
class TestSendRaisesNotification:
    def test_the_recipient_is_notified_and_the_sender_is_not(
        self, mock_site_context, site, django_capture_on_commit_callbacks
    ) -> None:
        sender, recipient = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(sender, recipient))

        with django_capture_on_commit_callbacks(execute=True):
            send_message(
                sender=sender,
                body="Hi",
                client_key=uuid.uuid4(),
                site=site,
                conversation=conversation,
            )

        notification = _message_notifications(recipient, conversation).get()
        assert notification.data == {"sender_name": sender.display_name}
        assert notification.site_id == site.pk
        assert not Notification.objects.filter(user=sender).exists()

    def test_two_sends_leave_one_unread_notification(
        self, mock_site_context, site, django_capture_on_commit_callbacks
    ) -> None:
        sender, recipient = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(sender, recipient))

        with django_capture_on_commit_callbacks(execute=True):
            for _ in range(2):
                send_message(
                    sender=sender,
                    body="Hi",
                    client_key=uuid.uuid4(),
                    site=site,
                    conversation=conversation,
                )

        assert _message_notifications(recipient, conversation).count() == 1

    def test_a_repeated_client_key_raises_nothing_more(
        self, mock_site_context, site, django_capture_on_commit_callbacks
    ) -> None:
        sender, recipient = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(sender, recipient))
        key = uuid.uuid4()
        with django_capture_on_commit_callbacks(execute=True):
            send_message(
                sender=sender,
                body="Hi",
                client_key=key,
                site=site,
                conversation=conversation,
            )
        Notification.objects.update(read_at=timezone.now())

        with django_capture_on_commit_callbacks(execute=True):
            send_message(
                sender=sender,
                body="Hi",
                client_key=key,
                site=site,
                conversation=conversation,
            )

        assert _message_notifications(recipient, conversation).count() == 1

    def test_a_deleted_other_participant_raises_nothing(
        self, mock_site_context, site, django_capture_on_commit_callbacks
    ) -> None:
        sender, recipient = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(sender, recipient))
        recipient.delete()

        with django_capture_on_commit_callbacks(execute=True):
            send_message(
                sender=sender,
                body="Hi",
                client_key=uuid.uuid4(),
                site=site,
                conversation=conversation,
            )

        assert not Notification.objects.exists()


@pytest.mark.django_db
class TestMarkConversationReadClearsNotification:
    def test_marking_the_conversation_read_reads_its_notification(
        self, mock_site_context
    ) -> None:
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        notification = NotificationFactory(
            user=user,
            category="message.received",
            target=conversation,
            data={"sender_name": "Sam"},
        )

        mark_conversation_read(
            user=user, conversation=conversation, up_to=timezone.now()
        )

        notification.refresh_from_db()
        assert notification.read_at is not None

    def test_a_newer_incoming_message_keeps_the_notification_unread(
        self, mock_site_context
    ) -> None:
        user, other = UserFactory(), UserFactory()
        conversation = ConversationFactory(between=(user, other))
        shown = MessageFactory(conversation=conversation, sender=other)
        MessageFactory(conversation=conversation, sender=other)
        notification = NotificationFactory(
            user=user,
            category="message.received",
            target=conversation,
            data={"sender_name": "Sam"},
        )

        mark_conversation_read(
            user=user, conversation=conversation, up_to=shown.created_at
        )

        notification.refresh_from_db()
        assert notification.read_at is None
