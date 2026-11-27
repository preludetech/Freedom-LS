"""Table filters for the audit log: who acted and what they did."""

from __future__ import annotations

from typing import cast

from panel_framework.filters import ChoiceFilter, TableFilter

from django.db.models import Q, QuerySet
from django.http import HttpRequest

from freedom_ls.accounts.models import User
from freedom_ls.audit_log.actions import audit_actions, audit_actions_by_group
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)

__all__ = [
    "AuditActionFilter",
    "AuditActorFilter",
]


class AuditActorFilter(TableFilter):
    """Narrows audit entries to one actor, or to the system.

    Choices are the users who acted on the request's organisation. An entry
    whose actor was deleted keeps only a stored name, so it matches "System"
    no more than it matches any user.
    """

    SYSTEM = "system"
    widget = "select"
    multiple = False

    def __init__(self) -> None:
        super().__init__("who", "Who")

    def get_choices(self, request: HttpRequest) -> list[tuple[str, str]]:
        scoped = cast("OrganisationScopedRequest", request)
        actors = User.objects.filter(
            pk__in=AuditLogEntry.objects.filter(
                organisation=scoped.organisation, actor__isnull=False
            ).values("actor_id")
        ).order_by("first_name", "last_name", "email")
        return [
            (self.SYSTEM, "System"),
            *((str(actor.pk), actor.display_name) for actor in actors),
        ]

    def apply(
        self, request: HttpRequest, queryset: QuerySet, values: list[str]
    ) -> QuerySet:
        condition = Q(actor_id__in=[v for v in values if v != self.SYSTEM])
        if self.SYSTEM in values:
            condition |= Q(actor__isnull=True, actor_label="")
        return queryset.filter(condition)


class AuditActionFilter(ChoiceFilter):
    """Narrows audit entries to the chosen actions, offering every registered
    action as a checklist under its group heading."""

    widget = "grouped_checklist"

    def __init__(self) -> None:
        super().__init__("what", "What", lookup="action")

    def get_choices(self, request: HttpRequest) -> list[tuple[str, str]]:
        return [(code, action.label) for code, action in audit_actions().items()]

    def get_groups(
        self, request: HttpRequest
    ) -> list[tuple[str, list[tuple[str, str]]]]:
        return [
            (group, [(action.code, action.label) for action in actions])
            for group, actions in audit_actions_by_group()
        ]
