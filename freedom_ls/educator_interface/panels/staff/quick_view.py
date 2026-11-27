"""The quick view of a staff member on the Staff table."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from panel_framework.quick_view import QuickView

from freedom_ls.educator_interface.events import STAFF_CHANGED
from freedom_ls.educator_interface.staff import current_role_entries
from freedom_ls.educator_interface.user_display import email_below_name

if TYPE_CHECKING:
    from freedom_ls.accounts.models import User
    from freedom_ls.educator_interface.panels.common.request import (
        OrganisationScopedRequest,
    )

__all__ = [
    "StaffQuickView",
]


class StaffQuickView(QuickView):
    """A staff member's roles, with who added each and when: detail the Staff
    table leaves out so its rows stay easy to scan."""

    template_name = "educator_interface/quick_views/staff.html"
    refresh_events = (STAFF_CHANGED,)

    def get_title(self) -> str:
        return cast("User", self.instance).display_name

    def get_subtitle(self) -> str:
        return email_below_name(cast("User", self.instance))

    def get_context_data(self) -> dict[str, object]:
        request = cast("OrganisationScopedRequest", self.request)
        return {
            "entries": current_role_entries(
                cast("User", self.instance), request.organisation
            )
        }
