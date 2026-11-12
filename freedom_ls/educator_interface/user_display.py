"""How the educator interface shows a person under their name."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from freedom_ls.accounts.models import User


def email_below_name(user: User) -> str:
    """The email to show on a line under the user's display name.

    Empty for an account with no name, because its display name is already
    the email and a second line would repeat it.
    """
    if user.display_name == user.email:
        return ""
    return user.email
