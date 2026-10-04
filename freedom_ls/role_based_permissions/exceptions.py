"""Exceptions raised when a role change is refused."""

from __future__ import annotations

from enum import StrEnum


class RefusalReason(StrEnum):
    SELF = "self"
    INACTIVE_USER = "inactive_user"
    NOT_PERMITTED = "not_permitted"
    LAST_SITE_ADMIN = "last_site_admin"
    LAST_ORGANISATION_ADMIN = "last_organisation_admin"


class RoleChangeRefused(Exception):  # noqa: N818 - callers catch this name, so it is public API
    """A role assignment or removal was refused. See RefusalReason for why."""

    def __init__(self, reason: RefusalReason) -> None:
        self.reason = reason
        super().__init__(reason)
