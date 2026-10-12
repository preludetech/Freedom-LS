from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import factory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.comms.models import (
    Conversation,
    ConversationParticipant,
    Message,
    Notification,
)
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.site_aware_models.factories import SiteAwareFactory

if TYPE_CHECKING:
    from freedom_ls.accounts.models import User


class NotificationFactory(SiteAwareFactory):
    class Meta:
        model = Notification

    user = factory.SubFactory(UserFactory)
    category = "course.registered"
    target = factory.SubFactory(CourseFactory)
    data = factory.LazyAttribute(lambda n: {"course_title": n.target.title})


class ConversationFactory(SiteAwareFactory):
    """A conversation with no participants until `between` is given two users."""

    class Meta:
        model = Conversation
        skip_postgeneration_save = True

    pair_key = factory.Sequence(lambda n: f"unpaired:{n}")

    @factory.post_generation
    def between(
        self: Conversation,
        create: bool,
        extracted: tuple[User, User] | None,
        **kwargs: object,
    ) -> None:
        """Pair the conversation with two users: writes `pair_key` and both
        participant rows."""
        if not create or extracted is None:
            return
        user_a, user_b = extracted
        self.pair_key = f"{min(user_a.pk, user_b.pk)}:{max(user_a.pk, user_b.pk)}"
        self.save(update_fields=["pair_key"])
        for user in extracted:
            ConversationParticipantFactory(conversation=self, user=user, site=self.site)


class ConversationParticipantFactory(SiteAwareFactory):
    class Meta:
        model = ConversationParticipant

    conversation = factory.SubFactory(ConversationFactory)
    user = factory.SubFactory(UserFactory)


class MessageFactory(SiteAwareFactory):
    class Meta:
        model = Message
        skip_postgeneration_save = True

    conversation = factory.SubFactory(ConversationFactory)
    sender = factory.LazyAttribute(
        lambda m: m.conversation.participants.select_related("user").first().user
    )
    body = factory.Sequence(lambda n: f"Message {n}")
    client_key = factory.LazyFunction(uuid.uuid4)

    @factory.post_generation
    def touch_conversation(self: Message, create: bool, extracted: object) -> None:
        if not create:
            return
        self.conversation.last_message_at = self.created_at
        self.conversation.save(update_fields=["last_message_at"])
