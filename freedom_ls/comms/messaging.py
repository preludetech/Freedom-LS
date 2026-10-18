"""Direct messaging: the pairing of two users into a conversation, and sending.

Every create passes ``site`` explicitly and every lookup filters on it, so the
functions here work outside a request (a worker, a shell) as well as inside one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, cast
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import (
    BooleanField,
    Case,
    Exists,
    F,
    FilteredRelation,
    Prefetch,
    Q,
    QuerySet,
    Value,
    When,
)
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from freedom_ls.comms.config import config
from freedom_ls.comms.messaging_loader import get_messaging_policy
from freedom_ls.comms.messaging_policy import (
    MessagingDecision,
    MessagingRefusal,
    RecipientGroup,
)
from freedom_ls.comms.models import Conversation, ConversationParticipant, Message
from freedom_ls.comms.notify import mark_notifications_read, raise_notification

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.contrib.sites.models import Site
    from django.db.models import Model

    from freedom_ls.accounts.models import User

BLANK_BODY = _("Type a message first.")
# Up to this many candidates the picker lists everyone without a search term.
PICKER_LIST_ALL_LIMIT = 15
PICKER_MIN_TERM_LENGTH = 2
PICKER_RESULT_LIMIT = 20
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


def inbox_for(user: User) -> QuerySet[Conversation]:
    """The user's conversations, newest activity first, ready to render as rows.

    The read marker comes through a filtered relation on the user's own
    participant row, so ``viewer_last_read_at`` and ``is_unread`` can never read
    the other participant's marker. The other participant is prefetched into
    ``other_participants`` so ``other_participant`` costs no query per row.
    """
    queryset = (
        Conversation.objects.annotate(
            mine=FilteredRelation("participants", condition=Q(participants__user=user))
        )
        .filter(mine__isnull=False)
        .annotate(viewer_last_read_at=F("mine__last_read_at"))
        .annotate(
            # A Case, not the bare Q: comparing against a null marker yields SQL
            # NULL, and the flag has to be a plain True or False.
            is_unread=Case(
                When(
                    Q(last_message_at__gt=F("viewer_last_read_at"))
                    | Q(
                        viewer_last_read_at__isnull=True, last_message_at__isnull=False
                    ),
                    then=Value(True),
                ),
                default=Value(False),
                output_field=BooleanField(),
            )
        )
        .select_related("site")
        .prefetch_related(
            Prefetch(
                "participants",
                queryset=ConversationParticipant.objects.exclude(
                    user=user
                ).select_related("user"),
                to_attr="other_participants",
            )
        )
        .order_by(F("last_message_at").desc(nulls_last=True), "-created_at")
    )
    return cast("QuerySet[Conversation]", queryset)


def unread_conversation_count(user: User) -> int:
    """How many conversations hold a message the user has not been shown."""
    return inbox_for(user).filter(Q(is_unread=True)).count()


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


def reply_decisions(
    *, viewer: User, conversations: Sequence[Conversation]
) -> dict[UUID, MessagingDecision]:
    """``reply_decision`` for each conversation, keyed by pk, in one policy call.

    A conversation whose other participant was deleted refuses without asking
    the policy; the rest go to the policy together, so the number of queries does
    not follow the number of conversations.
    """
    decisions: dict[UUID, MessagingDecision] = {}
    pairs: list[tuple[Conversation, User]] = []
    for conversation in conversations:
        other = other_participant(conversation, viewer)
        if other is None:
            decisions[conversation.pk] = MessagingDecision.refuse(
                MessagingRefusal.INACTIVE_USER
            )
        else:
            pairs.append((conversation, other))
    if pairs:
        decisions.update(
            get_messaging_policy().can_reply_many(
                sender=viewer, pairs=pairs, site=pairs[0][0].site
            )
        )
    return decisions


def mark_conversation_read(
    *, user: User, conversation: Conversation, up_to: datetime
) -> bool:
    """Advance the user's read marker to ``up_to``; it never moves backwards.

    Returns whether the marker moved, so a caller can tell the page its unread
    counts changed.

    The conversation's notification is marked read too, unless a message from
    someone else is newer than ``up_to``: that message has refreshed the
    notification and has not been shown. The reverse does not hold: reading or
    unreading a notification leaves the marker alone.
    """
    moved = ConversationParticipant.objects.filter(
        Q(last_read_at__isnull=True) | Q(last_read_at__lt=up_to),
        conversation=conversation,
        user=user,
    ).update(last_read_at=up_to)
    newer_incoming = Message.objects.filter(
        conversation=conversation, created_at__gt=up_to
    ).exclude(sender=user)
    mark_notifications_read(
        user=user,
        target=conversation,
        site_id=conversation.site_id,
        condition=~Q(Exists(newer_incoming)),
    )
    return moved > 0


def _has_unread_incoming(conversation: Conversation, user: User) -> bool:
    """Whether a message from someone else is newer than the user's read marker."""
    last_read_at = (
        ConversationParticipant.objects.filter(conversation=conversation, user=user)
        .values_list("last_read_at", flat=True)
        .first()
    )
    incoming = Message.objects.filter(conversation=conversation).exclude(sender=user)
    if last_read_at is not None:
        incoming = incoming.filter(created_at__gt=last_read_at)
    return incoming.exists()


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
        # The sender has read their own message, but not one that arrived
        # since they last looked: that stays unread until something shows it.
        if not _has_unread_incoming(locked, sender):
            mark_conversation_read(
                user=sender, conversation=locked, up_to=message.created_at
            )
        other = other_participant(locked, sender)
        if other is not None:
            raise_notification(
                user=other,
                category="message.received",
                target=locked,
                site_id=locked.site_id,
                data={"sender_name": sender.display_name},
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


def unreachable_recipient_alert_copy() -> str:
    """The refusal line for a recipient the sender isn't offered.

    It names no one, so it reads the same whoever the posted id belongs to.
    """
    return str(
        _(
            "Not sent. This person can't receive messages from you here. "
            "Your text is still in the box."
        )
    )


def closed_note_copy(
    reason: MessagingRefusal | None, other: User | None
) -> tuple[str, str]:
    """The heading and body of the note that stands in for a closed thread's composer."""
    heading = str(_("Replies are closed"))
    if other is not None and reason in (
        MessagingRefusal.CLOSED_BY_CONFIGURATION,
        MessagingRefusal.NO_RELATIONSHIP,
    ):
        name = other.first_name or other.display_name
        if reason == MessagingRefusal.CLOSED_BY_CONFIGURATION:
            body = _(
                "Messaging between you and %(name)s is closed here. "
                "You can both still read this conversation."
            )
        else:
            body = _(
                "You can no longer message %(name)s from here. "
                "You can both still read this conversation."
            )
        return heading, str(body % {"name": name})
    return heading, str(
        _("This conversation can't take new messages. You can still read it.")
    )


def encode_cursor(message: Message) -> str:
    """A position in the thread, safe to carry in a query string with ``|urlencode``."""
    return f"{message.created_at.isoformat()}~{message.pk}"


def decode_cursor(value: str) -> tuple[datetime, UUID] | None:
    """The position ``value`` names, or None when it is not a cursor."""
    stamp, separator, raw_pk = value.rpartition("~")
    if not separator:
        return None
    try:
        return datetime.fromisoformat(stamp), UUID(raw_pk)
    except ValueError:
        return None


def _message_page(
    conversation: Conversation,
    *,
    before: tuple[datetime, UUID] | None = None,
    after: tuple[datetime, UUID] | None = None,
    limit: int,
) -> list[Message]:
    """Up to ``limit`` messages strictly before or after a position, nearest first.

    Ordered by ``(created_at, id)`` so messages sharing a timestamp keep a
    stable order and a keyset position never skips or repeats one. With
    neither bound the newest messages are returned. ``before`` and ``after``
    are exclusive of the message at the position.
    """
    queryset = Message.objects.filter(conversation=conversation).select_related(
        "sender"
    )
    if before is not None:
        stamp, pk = before
        queryset = queryset.filter(
            Q(created_at__lt=stamp) | Q(created_at=stamp, id__lt=pk)
        )
    if after is not None:
        stamp, pk = after
        queryset = queryset.filter(
            Q(created_at__gt=stamp) | Q(created_at=stamp, id__gt=pk)
        )
    ordering = ("created_at", "id") if after is not None else ("-created_at", "-id")
    return list(queryset.order_by(*ordering)[:limit])


def _page_with_more(
    conversation: Conversation, before: tuple[datetime, UUID] | None
) -> tuple[list[Message], bool]:
    """A page of messages oldest first, and whether older ones remain.

    One row beyond the page size is fetched to learn whether more exist.
    """
    fetched = _message_page(
        conversation, before=before, limit=config.MESSAGE_PAGE_SIZE + 1
    )
    has_more = len(fetched) > config.MESSAGE_PAGE_SIZE
    page = fetched[: config.MESSAGE_PAGE_SIZE]
    page.reverse()
    return page, has_more


def latest_page(conversation: Conversation) -> tuple[list[Message], bool]:
    """The newest page of messages, oldest first, and whether older ones remain."""
    return _page_with_more(conversation, None)


def latest_messages(conversation: Conversation, limit: int) -> list[Message]:
    """The newest ``limit`` messages, oldest first."""
    messages = _message_page(conversation, limit=limit)
    messages.reverse()
    return messages


def page_before(
    conversation: Conversation, cursor: tuple[datetime, UUID]
) -> tuple[list[Message], bool]:
    """The page of messages just older than ``cursor``, oldest first, and whether more remain."""
    return _page_with_more(conversation, cursor)


# Sorts before every real message, so no cursor means "from the first message".
_START_OF_THREAD = (datetime.min.replace(tzinfo=UTC), UUID(int=0))


def messages_after(
    conversation: Conversation, cursor: tuple[datetime, UUID] | None
) -> list[Message]:
    """The messages strictly newer than ``cursor``, oldest first.

    At most one page is returned; a longer backlog arrives over the next polls,
    each of which moves the cursor to the last message it carried. ``None``
    starts from the first message of the thread.
    """
    return _message_page(
        conversation,
        after=cursor if cursor is not None else _START_OF_THREAD,
        limit=config.MESSAGE_PAGE_SIZE,
    )


def new_messages_announcement(count: int, sender_name: str) -> str:
    """The polite screen-reader line for messages that arrived while the thread was open."""
    return ngettext(
        "%(count)d new message from %(name)s",
        "%(count)d new messages from %(name)s",
        count,
    ) % {"count": count, "name": sender_name}


@dataclass(frozen=True, slots=True)
class MessageEntry:
    """A message with what its log entry shows around it."""

    message: Message
    show_day: bool
    show_sender: bool


def render_message_entries(
    messages: list[Message], previous: Message | None
) -> list[MessageEntry]:
    """Entries for ``messages`` (oldest first) judged against the message before them.

    A day separator shows when the local date differs from the previous
    message's, and the sender line shows when the sender or the day changes.
    ``previous`` is None for the first message of the thread.
    """
    entries: list[MessageEntry] = []
    for message in messages:
        if previous is None:
            show_day = show_sender = True
        else:
            show_day = _local_day(message) != _local_day(previous)
            show_sender = show_day or message.sender_id != previous.sender_id
        entries.append(MessageEntry(message, show_day, show_sender))
        previous = message
    return entries


def _local_day(message: Message) -> date:
    return timezone.localtime(message.created_at).date()


def entry_for_message(message: Message) -> MessageEntry:
    """The entry for one message, judged against the message just before it."""
    older = _message_page(
        message.conversation,
        before=(message.created_at, message.pk),
        limit=1,
    )
    return render_message_entries([message], older[0] if older else None)[0]


@dataclass(frozen=True, slots=True)
class RecipientSearch:
    """What the picker shows: grouped people, or a prompt to type more."""

    groups: list[RecipientGroup]
    truncated: bool = False
    needs_term: bool = False

    @property
    def count(self) -> int:
        return sum(len(group.users) for group in self.groups)


def search_recipients(
    *,
    sender: User,
    site: Site,
    term: str,
    include_email: bool,
    candidates: QuerySet[User] | None = None,
    scope: Model | None = None,
) -> RecipientSearch:
    """Narrow the people ``sender`` may message to those matching ``term``.

    Only narrows ``candidates`` (default: everyone the policy offers the
    sender); a person outside them never appears, so a name the sender may not
    message looks the same as a name that does not exist. A short list is shown
    whole; a longer one waits for a term of two characters. Results are capped
    at 20, with ``truncated`` set when more matched.
    """
    policy = get_messaging_policy()
    if candidates is None:
        candidates = policy.recipients_for(sender=sender, site=site)
    term = term.strip()
    if not term:
        everyone = list(
            candidates.order_by("first_name", "last_name", "pk")[
                : PICKER_LIST_ALL_LIMIT + 1
            ]
        )
        if len(everyone) > PICKER_LIST_ALL_LIMIT:
            return RecipientSearch(groups=[], needs_term=True)
        matches, truncated = everyone, False
    elif len(term) < PICKER_MIN_TERM_LENGTH:
        return RecipientSearch(groups=[], needs_term=True)
    else:
        # Every word must match some field, so "Jane Smith" finds Jane Smith.
        condition = Q()
        for word in term.split():
            word_condition = Q(first_name__icontains=word) | Q(
                last_name__icontains=word
            )
            if include_email:
                word_condition |= Q(email__icontains=word)
            condition &= word_condition
        fetched = list(
            candidates.filter(condition).order_by("first_name", "last_name", "pk")[
                : PICKER_RESULT_LIMIT + 1
            ]
        )
        truncated = len(fetched) > PICKER_RESULT_LIMIT
        matches = fetched[:PICKER_RESULT_LIMIT]
    if not matches:
        return RecipientSearch(groups=[])
    groups = policy.group_recipients(
        sender=sender, site=site, recipients=matches, scope=scope
    )
    return RecipientSearch(groups=groups, truncated=truncated)
