"""The default messaging policy."""

from __future__ import annotations

from typing import TYPE_CHECKING

from freedom_ls.accounts.models import User
from freedom_ls.comms.messaging_policy import (
    MessagingDecision,
    MessagingPolicy,
    MessagingRefusal,
)
from freedom_ls.learner_management.capabilities import roles_granting
from freedom_ls.learner_management.models import Learner
from freedom_ls.learner_management.queries import (
    VIEW_LEARNER,
    visible_learners_expression,
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
        if self._related_users(sender, site).filter(pk=recipient.pk).exists():
            return MessagingDecision.allow()
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
        return self._related_users(sender, site)

    def _related_users(self, sender: User, site: Site) -> QuerySet[User]:
        """Users the sender may start a conversation with on this site, as one
        queryset of pk__in subqueries so it needs no distinct() and stays filterable."""
        roles = roles_granting(VIEW_LEARNER, site)
        visible_learners = Learner.objects.filter(site=site, is_active=True).filter(
            visible_learners_expression(sender, roles, site)
        )
        return (
            User.objects.filter(site=site, is_active=True)
            .exclude(pk=sender.pk)
            .filter(pk__in=visible_learners.values("user_id"))
        )
