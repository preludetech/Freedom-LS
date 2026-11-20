"""The role filter for the educator interface's Staff table."""

from __future__ import annotations

from typing import cast

from django.db.models import QuerySet
from django.http import HttpRequest

from freedom_ls.accounts.models import User
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.queries import (
    STAFF_ROLES,
    VIEW_ORGANISATION_STAFF_ROLES,
    staff_assignments,
)
from freedom_ls.panel_framework.filters import ChoiceFilter
from freedom_ls.role_based_permissions.loader import get_role_config

__all__ = [
    "StaffRoleFilter",
    "may_see_staff_roles",
]


def may_see_staff_roles(request: HttpRequest) -> bool:
    """Whether the viewer may see which roles staff members hold, computed once
    and kept on the request because the roles cell, the Role filter's choices
    and its narrowing all ask. A viewer who may see names only must not learn
    who holds which role, so the filter withholds itself too."""
    scoped = cast("OrganisationScopedRequest", request)
    cached = getattr(scoped, "may_see_staff_roles", None)
    if cached is None:
        cached = can(scoped.user, VIEW_ORGANISATION_STAFF_ROLES, scoped.organisation)
        scoped.may_see_staff_roles = cached
    return cached


class StaffRoleFilter(ChoiceFilter):
    """Narrows staff to those holding a chosen role here; every role while
    the parameter is absent or "All roles" is among the values."""

    ALL = "all"
    widget = "select"

    def __init__(self) -> None:
        super().__init__("role", "Role", default=(self.ALL,), always_shown=True)

    def get_choices(self, request: HttpRequest) -> list[tuple[str, str]]:
        if not may_see_staff_roles(request):
            return []
        scoped = cast("OrganisationScopedRequest", request)
        config = get_role_config(scoped.organisation.site.name)
        return [
            (self.ALL, "All roles"),
            # A site that replaces the roles may leave some of these out.
            *(
                (role, config[role].display_name)
                for role in STAFF_ROLES
                if role in config
            ),
        ]

    def toggled(self, values: list[str], value: str) -> list[str]:
        # "All roles" is the no-selection state: picking a role replaces it,
        # and picking it replaces any roles.
        if value == self.ALL:
            return [self.ALL]
        return super().toggled([v for v in values if v != self.ALL], value)

    def apply(
        self, request: HttpRequest, queryset: QuerySet[User], values: list[str]
    ) -> QuerySet[User]:
        # "All roles" beside a role still means every role.
        if self.ALL in values or not may_see_staff_roles(request):
            return queryset
        scoped = cast("OrganisationScopedRequest", request)
        return queryset.filter(
            pk__in=staff_assignments(scoped.organisation)
            .filter(role__in=values)
            .values("user_id")
        )
