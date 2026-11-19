"""The status badges for an `is_active` flag."""

from __future__ import annotations

from freedom_ls.panel_framework.views import StatusBadge

__all__ = [
    "active_status_badge",
    "inactive_badge",
]


def active_status_badge(is_active: bool) -> StatusBadge:
    """The badge for an `is_active` flag, shown by `<c-panel-status-badge>`."""
    if is_active:
        return StatusBadge("success", "Active")
    return StatusBadge("muted", "Inactive")


def inactive_badge(is_active: bool) -> StatusBadge | None:
    """A page header's badge for an `is_active` flag: Active is the default
    state and shows nothing, so only Inactive is drawn."""
    if is_active:
        return None
    return StatusBadge("muted", "Inactive")
