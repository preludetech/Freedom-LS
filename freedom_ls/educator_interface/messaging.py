"""The educator interface's slice of the direct-messaging inbox."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from django.db.models import Exists, F, OuterRef, Prefetch

from freedom_ls.comms.messaging import (
    inbox_for,
    last_message_body_subquery,
    pair_key_for,
    reply_decision,
)
from freedom_ls.comms.messaging_loader import get_messaging_policy
from freedom_ls.comms.models import Conversation, ConversationParticipant
from freedom_ls.learner_management.queries import educators_of
from freedom_ls.site_aware_models.models import get_cached_site

if TYPE_CHECKING:
    from django.contrib.sites.models import Site
    from django.db.models import QuerySet
    from django.http import HttpRequest

    from freedom_ls.accounts.models import User
    from freedom_ls.learner_management.models import Learner


@dataclass(frozen=True, slots=True)
class OwnConversation:
    """The signed-in educator's side of messaging one learner: the conversation
    they already share, if any, and whether the policy lets them write."""

    conversation: Conversation | None
    allowed: bool


def own_conversation_with(request: HttpRequest, learner: Learner) -> OwnConversation:
    """The educator's own conversation with the learner and whether they may write.

    The policy's reply decision applies once a conversation exists, its start
    decision before then.
    """
    educator = cast("User", request.user)
    conversation = (
        inbox_for(educator)
        .filter(pair_key=pair_key_for(educator, learner.user))
        .first()
    )
    if conversation is not None:
        decision = reply_decision(viewer=educator, conversation=conversation)
    else:
        decision = get_messaging_policy().can_start(
            sender=educator,
            recipient=learner.user,
            site=cast("Site", get_cached_site(request)),
        )
    return OwnConversation(conversation, decision.allowed)


def oversight_conversations_for(learner: Learner) -> QuerySet[Conversation]:
    """The learner's conversations whose other participant is one of their
    educators now, newest activity first, with an excerpt and the educator
    prefetched. A conversation with someone who has since lost their educator
    role is not in it, and a deactivated learner has none, since educators_of
    is empty for them."""
    educator_ids = educators_of(learner).values("pk")
    learner_side = ConversationParticipant.objects.filter(
        conversation=OuterRef("pk"), user=learner.user
    )
    educator_side = ConversationParticipant.objects.filter(
        conversation=OuterRef("pk"), user__in=educator_ids
    ).exclude(user=learner.user)
    conversations: QuerySet[Conversation] = (
        Conversation.objects.filter(Exists(learner_side), Exists(educator_side))
        .annotate(last_message_body=last_message_body_subquery())
        .prefetch_related(
            Prefetch(
                "participants",
                queryset=ConversationParticipant.objects.exclude(
                    user=learner.user
                ).select_related("user"),
                to_attr="other_participants",
            )
        )
        .order_by(F("last_message_at").desc(nulls_last=True), "-created_at")
    )
    return conversations
