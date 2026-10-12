"""The contract every messaging surface asks before it lets one user message another."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.contrib.sites.models import Site
    from django.db.models import Model, QuerySet

    from freedom_ls.accounts.models import User
    from freedom_ls.comms.models import Conversation


class MessagingRefusal(StrEnum):
    SAME_USER = "same_user"
    INACTIVE_USER = "inactive_user"
    # The pair shares no cohort, course, organisation or educator on this site.
    NO_RELATIONSHIP = "no_relationship"
    # The pair is related, but no shared context is configured open.
    CLOSED_BY_CONFIGURATION = "closed_by_configuration"
    # TODO: add a block reason here when user blocking exists.


@dataclass(frozen=True, slots=True)
class MessagingDecision:
    allowed: bool
    reason: MessagingRefusal | None = None

    def __post_init__(self) -> None:
        if self.allowed == (self.reason is not None):
            raise ValueError(
                "an allowed decision carries no reason; a refusal carries one"
            )

    def __bool__(self) -> bool:
        # A dataclass instance is truthy, so `if policy.can_start(...)` would pass
        # every refusal. Force callers to read .allowed.
        raise TypeError("use .allowed")

    @classmethod
    def allow(cls) -> MessagingDecision:
        return cls(allowed=True)

    @classmethod
    def refuse(cls, reason: MessagingRefusal) -> MessagingDecision:
        return cls(allowed=False, reason=reason)


@dataclass(frozen=True, slots=True)
class RecipientGroup:
    """A labelled run of people in the recipient picker; an empty label is no heading."""

    label: str
    users: list[User]


class MessagingPolicy:
    """Answers "may this user message that user?" for every messaging surface.

    A plain class rather than an abc.ABC, like CourseAccessBackend. A downstream
    subclass that forgets a method fails on first use, not at import. Instances
    are stateless and never cache an answer.
    """

    def can_start(
        self, *, sender: User, recipient: User, site: Site
    ) -> MessagingDecision:
        raise NotImplementedError

    def can_reply(
        self, *, sender: User, recipient: User, site: Site, conversation: Conversation
    ) -> MessagingDecision:
        raise NotImplementedError

    def recipients_for(self, *, sender: User, site: Site) -> QuerySet[User]:
        raise NotImplementedError

    def group_recipients(
        self,
        *,
        sender: User,
        site: Site,
        recipients: Sequence[User],
        scope: Model | None = None,
    ) -> list[RecipientGroup]:
        """Arrange ``recipients`` under headings for the picker.

        ``scope`` narrows the headings to one context, such as an organisation.
        The base policy has no structure to group by, so it returns one group
        with no heading.
        """
        return [RecipientGroup(label="", users=list(recipients))]
