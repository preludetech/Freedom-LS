"""The progress and at-risk flag badges and the report over-limit message."""

from __future__ import annotations

from panel_framework.views import StatusBadge

from freedom_ls.learner_management.models import Cohort
from freedom_ls.learner_management.queries import cohort_learner_count
from freedom_ls.reports.config import config as reports_config
from freedom_ls.reports.report_data import AtRiskFlag, over_limit_message
from freedom_ls.reports.statuses import ProgressStatus, progress_status

__all__ = [
    "PROGRESS_STATUS_TONES",
    "flag_badge",
    "progress_status_badge",
    "report_over_limit_message",
]

PROGRESS_STATUS_TONES = {
    ProgressStatus.NOT_STARTED: "muted",
    ProgressStatus.IN_PROGRESS: "info",
    ProgressStatus.COMPLETE: "success",
}


def progress_status_badge(completion_percentage: int) -> StatusBadge:
    """The badge for a learner's progress status, from a recomputed completion."""
    status = progress_status(completion_percentage)
    return StatusBadge(tone=PROGRESS_STATUS_TONES[status], label=status.label)


def flag_badge(flag: AtRiskFlag) -> StatusBadge:
    """The badge for an at-risk flag."""
    # A rule's severity is already a role token name, so it is the tone.
    return StatusBadge(tone=flag.severity, label=flag.label)


def report_over_limit_message(cohort: Cohort) -> str:
    """Why no report can be generated for `cohort`, or "" while it is within the limit.

    The limit is a resource guard the task enforces when it builds the
    roster; checking the active learner count up front keeps the Downloads
    card from offering a report that can only fail.
    """
    learner_count = cohort_learner_count(cohort)
    limit = reports_config.REPORTS_MAX_LEARNERS
    if learner_count <= limit:
        return ""
    return over_limit_message(cohort.name, learner_count, limit)
