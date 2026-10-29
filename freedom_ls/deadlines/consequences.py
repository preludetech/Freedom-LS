from __future__ import annotations

from datetime import datetime

from freedom_ls.deadlines.policy import ResolvedDeadlinePolicy
from freedom_ls.deadlines.resolver import ResolvedDeadline, is_overdue


def shows_overdue(
    resolved: ResolvedDeadline,
    policy: ResolvedDeadlinePolicy,
    completed: bool,
    now: datetime,
) -> bool:
    """Whether the overdue mark shows: the item is overdue and the policy marks overdue items."""
    return policy.mark_overdue and is_overdue(resolved, completed, now)


def access_end_instant(
    time_limit: ResolvedDeadline, policy: ResolvedDeadlinePolicy
) -> datetime | None:
    """When the learner's access ends: the time limit plus the grace window. None when the
    policy does not end access or the course has no time limit."""
    if not policy.end_course_access or time_limit.due_at is None:
        return None
    return time_limit.due_at + policy.grace_window
