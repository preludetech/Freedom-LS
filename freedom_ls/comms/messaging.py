"""Direct messaging: the pairing of two users into a conversation, and sending.

Every create passes ``site`` explicitly and every lookup filters on it, so the
functions here work outside a request (a worker, a shell) as well as inside one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, cast
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Value
from django.db.models.functions import Coalesce, Greatest
from django.utils.translation import gettext_lazy as _

from freedom_ls.comms.config import config
from freedom_ls.comms.messaging_loader import get_messaging_policy
from freedom_ls.comms.messaging_policy import MessagingDecision, MessagingRefusal
from freedom_ls.comms.models import Conversation, ConversationParticipant, Message

if TYPE_CHECKING:
    from django.contrib.sites.models import Site

    from freedom_ls.accounts.models import User

BLANK_BODY = _("Type a message first.")
TOO_LONG_BODY = _("This message is too long. The limit is %(limit)s characters.")


@dataclass(frozen=True, slots=True)
class SendResult:
    message: Message | None = None
    conversation: Conversation | None = None
    refusal: MessagingRefusal | None = None
    body_error: str | None = None


def pair_key_for(user_a: User, user_b: User) -> str:
    return f"{min(user_a.pk, user_b.pk)}:{max(user_a.pk, user_b.pk)}"


def conversation_between(user_a: User, user_b: User, site: Site) -> Conversation | None:
    return Conversation.objects.filter(
        site=site, pair_key=pair_key_for(user_a, user_b)
    ).first()


def get_or_create_conversation(
    *, user_a: User, user_b: User, site: Site
) -> Conversation:
    existing = conversation_between(user_a, user_b, site)
    if existing is not None:
        return existing
    try:
        with transaction.atomic():
            conversation = Conversation.objects.create(
                site=site, pair_key=pair_key_for(user_a, user_b)
            )
            for user in (user_a, user_b):
                ConversationParticipant.objects.create(
                    site=site, conversation=conversation, user=user
                )
    except IntegrityError:
        # Two first messages raced; the row the other transaction committed is
        # the conversation.
        return cast(
            "Conversation",
            Conversation.objects.get(site=site, pair_key=pair_key_for(user_a, user_b)),
        )
    return cast("Conversation", conversation)


def other_participant(conversation: Conversation, viewer: User) -> User | None:
    """The participant who is not ``viewer``; None once that account was deleted.

    Reads the prefetched ``other_participants`` rows when the conversation came
    from a query that loaded them, else makes one query.
    """
    prefetched: list[ConversationParticipant] | None = getattr(
        conversation, "other_participants", None
    )
    if prefetched is not None:
        return prefetched[0].user if prefetched else None
    row = conversation.participants.exclude(user=viewer).select_related("user").first()
    return row.user if row is not None else None


def reply_decision(*, viewer: User, conversation: Conversation) -> MessagingDecision:
    other = other_participant(conversation, viewer)
    if other is None:
        return MessagingDecision.refuse(MessagingRefusal.INACTIVE_USER)
    return get_messaging_policy().can_reply(
        sender=viewer,
        recipient=other,
        site=conversation.site,
        conversation=conversation,
    )


def mark_conversation_read(
    *, user: User, conversation: Conversation, up_to: datetime
) -> None:
    """Advance the user's read marker to ``up_to``; it never moves backwards."""
    ConversationParticipant.objects.filter(conversation=conversation, user=user).update(
        last_read_at=Greatest(Coalesce("last_read_at", Value(up_to)), Value(up_to))
    )


def normalise_body(body: str) -> str:
    return body.replace("\r\n", "\n")


def _existing_send(
    conversation: Conversation, sender: User, client_key: UUID
) -> Message | None:
    return Message.objects.filter(
        conversation=conversation, sender=sender, client_key=client_key
    ).first()


def send_message(
    *,
    sender: User,
    body: str,
    client_key: UUID,
    site: Site,
    conversation: Conversation | None = None,
    recipient: User | None = None,
) -> SendResult:
    """Store ``body`` as a new message, or explain why it was not stored.

    Either ``conversation`` (a reply) or ``recipient`` (a first message, or a
    message to someone the sender may already have a conversation with) names
    where it goes. A ``client_key`` the sender already used in the conversation
    returns the original message.
    """
    body = normalise_body(body)
    if not body.strip():
        return SendResult(conversation=conversation, body_error=str(BLANK_BODY))
    if len(body) > config.MESSAGE_MAX_LENGTH:
        return SendResult(
            conversation=conversation,
            body_error=str(TOO_LONG_BODY % {"limit": config.MESSAGE_MAX_LENGTH}),
        )
    if conversation is None and recipient is not None:
        conversation = conversation_between(sender, recipient, site)
    if conversation is not None:
        repeat = _existing_send(conversation, sender, client_key)
        if repeat is not None:
            # A retry of a send that already landed is answered with the
            # original, whatever the policy says now.
            return SendResult(message=repeat, conversation=conversation)
        decision = reply_decision(viewer=sender, conversation=conversation)
    else:
        if recipient is None:
            raise ValueError("send_message needs a conversation or a recipient")
        decision = get_messaging_policy().can_start(
            sender=sender, recipient=recipient, site=site
        )
    if not decision.allowed:
        return SendResult(conversation=conversation, refusal=decision.reason)
    with transaction.atomic():
        if conversation is None:
            if recipient is None:
                raise ValueError("send_message needs a conversation or a recipient")
            conversation = get_or_create_conversation(
                user_a=sender, user_b=recipient, site=site
            )
        locked = Conversation.objects.select_for_update().get(pk=conversation.pk)
        # A same-key send may have committed while this one waited for the lock.
        repeat = _existing_send(locked, sender, client_key)
        if repeat is not None:
            return SendResult(message=repeat, conversation=locked)
        message = Message.objects.create(
            site=site,
            conversation=locked,
            sender=sender,
            body=body,
            client_key=client_key,
        )
        locked.last_message_at = message.created_at
        locked.save(update_fields=["last_message_at"])
        mark_conversation_read(
            user=sender, conversation=locked, up_to=message.created_at
        )
    return SendResult(message=message, conversation=locked)


def refusal_alert_copy(refusal: MessagingRefusal | None, other: User | None) -> str:
    """The line shown above a composer whose send was refused."""
    if other is None:
        return str(
            _(
                "Not sent. This conversation can't take new messages. "
                "Your text is still in the box."
            )
        )
    name = other.first_name or other.display_name
    return str(
        _(
            "Not sent. %(name)s can't receive messages from you here. "
            "Your text is still in the box."
        )
        % {"name": name}
    )


def latest_page(conversation: Conversation) -> list[Message]:
    """The newest page of messages, oldest first.

    Fetched newest-first to take the latest page, then reversed because the
    log reads oldest to newest.
    """
    newest_first = list(
        Message.objects.filter(conversation=conversation)
        .select_related("sender")
        .order_by("-created_at", "-id")[: config.MESSAGE_PAGE_SIZE]
    )
    newest_first.reverse()
    return newest_first
