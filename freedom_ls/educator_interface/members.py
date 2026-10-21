"""What the Members section shows about the roles a member holds."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, cast

from freedom_ls.learner_management.models import Cohort
from freedom_ls.learner_management.queries import MEMBER_ROLES
from freedom_ls.role_based_permissions.loader import get_role_config
from freedom_ls.role_based_permissions.models import ObjectRoleAssignment

if TYPE_CHECKING:
    from django.contrib.sites.models import Site

    from freedom_ls.accounts.models import User

ORGANISATION_SCOPE = "Whole organisation"
_NAMED_COHORTS = 2


@dataclass(frozen=True)
class RoleEntry:
    """One role a member holds in the organisation: its scope, and the
    newest grant that set who added it."""

    role: str
    display_name: str
    cohorts: tuple[Cohort, ...]  # empty for organisation_admin
    assigned_by: User | None
    assigned_at: datetime

    @property
    def scope(self) -> str:
        if self.role == "organisation_admin":
            return ORGANISATION_SCOPE
        names = [
            c.name if c.is_active else f"{c.name} (inactive)" for c in self.cohorts
        ]
        if len(names) <= _NAMED_COHORTS:
            return ", ".join(names)
        shown = ", ".join(names[:_NAMED_COHORTS])
        return f"{shown} +{len(names) - _NAMED_COHORTS} more"

    @property
    def full_scope(self) -> str:
        """Every cohort name, for a tooltip beside the shortened scope."""
        if self.role == "organisation_admin":
            return ORGANISATION_SCOPE
        return ", ".join(c.name for c in self.cohorts)


def member_role_entries(user: User, site: Site) -> list[RoleEntry]:
    """Reads only the held_assignments prefetch and each assignment's
    prefetched target, so a page costs the same as one row. Entries follow
    MEMBER_ROLES order; cohorts sort by name; the display names come from
    the site's role config."""
    # Set by the table's Prefetch(to_attr=...), so it is not a declared attribute.
    held = cast("list[ObjectRoleAssignment]", user.__dict__["held_assignments"])
    config = get_role_config(site.name)
    entries: list[RoleEntry] = []
    for role in MEMBER_ROLES:
        assignments = [a for a in held if a.role == role]
        if not assignments:
            continue
        newest = max(assignments, key=lambda a: a.assigned_at)
        cohorts: tuple[Cohort, ...] = ()
        if role != "organisation_admin":
            targets = [a.target for a in assignments if isinstance(a.target, Cohort)]
            if len(targets) != len(assignments):
                raise ValueError(
                    f"{role} is held on a cohort that no longer exists "
                    f"(user {user.pk})."
                )
            cohorts = tuple(sorted(targets, key=lambda c: c.name))
        entries.append(
            RoleEntry(
                role=role,
                display_name=config[role].display_name,
                cohorts=cohorts,
                assigned_by=newest.assigned_by,
                assigned_at=newest.assigned_at,
            )
        )
    return entries
