"""How a learner's last activity reads in the educator interface."""

from __future__ import annotations

from freedom_ls.accounts.models import User
from freedom_ls.base.date_display import display_date

__all__ = ["last_active_text"]


def last_active_text(user: User) -> str:
    """The date the user last made a signed-in request, or "Never"."""
    if user.last_active is None:
        return "Never"
    return display_date(user.last_active)
