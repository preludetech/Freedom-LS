"""The status badges for an `is_active` flag."""

from __future__ import annotations

from datetime import datetime

from panel_framework.views import StatusBadge

from freedom_ls.learner_management.models import Learner
from freedom_ls.learner_management.queries import LearnerStatus, learner_status

__all__ = [
    "_LEARNER_STATUS_TONES",
    "active_status_badge",
    "inactive_badge",
    "learner_status_badge",
    "retired_badge",
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


def retired_badge(retired_at: datetime | None) -> StatusBadge | None:
    """The badge for a retired content row. A live row shows nothing."""
    if retired_at is None:
        return None
    return StatusBadge("muted", "Retired")


_LEARNER_STATUS_TONES: dict[LearnerStatus, str] = {
    LearnerStatus.ACTIVE: "success",
    LearnerStatus.PENDING: "info",
    LearnerStatus.INACTIVE: "muted",
}


def learner_status_badge(learner: Learner) -> StatusBadge:
    """The badge for a learner's status: Active, Pending or Inactive."""
    status = learner_status(learner)
    return StatusBadge(_LEARNER_STATUS_TONES[status], status.label)
