"""Account setup state for users created by staff."""

from __future__ import annotations

from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX
from django.db.models import Q

from freedom_ls.accounts.models import User


def pending_user_q(prefix: str = "") -> Q:
    """Q matching users who have never logged in and cannot: staff-created
    accounts whose setup link is still the only way in."""
    return Q(
        **{
            f"{prefix}last_login__isnull": True,
            f"{prefix}password__startswith": UNUSABLE_PASSWORD_PREFIX,
        }
    )


def is_pending(user: User) -> bool:
    return user.last_login is None and not user.has_usable_password()
