"""The default messaging policy."""

from __future__ import annotations

from typing import TYPE_CHECKING

from freedom_ls.accounts.models import User
from freedom_ls.comms.messaging_policy import (
    MessagingDecision,
    MessagingPolicy,
    MessagingRefusal,
)

if TYPE_CHECKING:
    from django.contrib.sites.models import Site
    from django.db.models import Model, QuerySet


class LayeredMessagingPolicy(MessagingPolicy):
    def can_start(
        self, *, sender: User, recipient: User, site: Site
    ) -> MessagingDecision:
        if sender == recipient:
            return MessagingDecision.refuse(MessagingRefusal.SAME_USER)
        if not (sender.is_active and recipient.is_active):
            return MessagingDecision.refuse(MessagingRefusal.INACTIVE_USER)
        return MessagingDecision.refuse(MessagingRefusal.NO_RELATIONSHIP)

    def can_reply(
        self, *, sender: User, recipient: User, site: Site, conversation: Model
    ) -> MessagingDecision:
        # Reply rights are symmetric: whichever direction may start now keeps the
        # conversation open, so the conversation itself is not consulted.
        forward = self.can_start(sender=sender, recipient=recipient, site=site)
        if forward.allowed:
            return forward
        backward = self.can_start(sender=recipient, recipient=sender, site=site)
        return MessagingDecision.allow() if backward.allowed else forward

    def recipients_for(self, *, sender: User, site: Site) -> QuerySet[User]:
        return User.objects.none()
