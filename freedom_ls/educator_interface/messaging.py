"""The educator interface's slice of the direct-messaging inbox."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db.models import Exists, OuterRef

from freedom_ls.comms.messaging import inbox_for
from freedom_ls.comms.models import ConversationParticipant
from freedom_ls.learner_management.queries import learners_visible_to

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from freedom_ls.accounts.models import User
    from freedom_ls.comms.models import Conversation
    from freedom_ls.organisations.models import Organisation


def conversations_in_organisation(
    user: User, organisation: Organisation
) -> QuerySet[Conversation]:
    """The user's own conversations whose other participant is a learner they can see here.

    A conversation with a colleague, with a learner of another organisation, or
    with a learner outside the user's cohorts is not part of this organisation's
    section. A conversation whose other participant was deleted has no such
    participant, so it is absent too.
    """
    visible_user_ids = learners_visible_to(user, organisation).values("user_id")
    other = ConversationParticipant.objects.filter(
        conversation=OuterRef("pk"), user__in=visible_user_ids
    ).exclude(user=user)
    return inbox_for(user).filter(Exists(other))


@dataclass(frozen=True, slots=True)
class ConversationRow:
    """One row of the section's table: the conversation, who it is with, and
    whether the educator may still reply."""

    conversation: Conversation
    other: User | None
    can_reply: bool

    @property
    def name(self) -> str:
        return self.other.display_name if self.other is not None else "Deleted user"

    def __str__(self) -> str:
        return self.name
