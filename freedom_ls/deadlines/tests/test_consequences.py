from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from freedom_ls.deadlines.consequences import access_end_instant, shows_overdue
from freedom_ls.deadlines.models import AfterAccessEnded
from freedom_ls.deadlines.policy import ResolvedDeadlinePolicy
from freedom_ls.deadlines.resolver import NO_DEADLINE, DeadlineSource, ResolvedDeadline

DUE = datetime(2026, 3, 20, 12, 0, tzinfo=UTC)


def _policy(
    *,
    mark_overdue: bool = True,
    end_course_access: bool = False,
    grace_window: timedelta = timedelta(0),
) -> ResolvedDeadlinePolicy:
    return ResolvedDeadlinePolicy(
        mark_overdue=mark_overdue,
        close_items=False,
        end_course_access=end_course_access,
        notify_educators=False,
        grace_window=grace_window,
        after_access_ended=AfterAccessEnded.OUTLINE_AND_RESULTS,
        sources={},
    )


def _resolved(due_at: datetime | None) -> ResolvedDeadline:
    return ResolvedDeadline(due_at, DeadlineSource.CONTENT)


@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        (timedelta(seconds=-1), False),
        (timedelta(0), False),
        (timedelta(seconds=1), True),
    ],
)
def test_shows_overdue_turns_on_after_the_due_instant(offset, expected):
    assert shows_overdue(_resolved(DUE), _policy(), False, DUE + offset) is expected


def test_shows_overdue_is_false_for_a_completed_item():
    now = DUE + timedelta(days=1)

    assert shows_overdue(_resolved(DUE), _policy(), True, now) is False


def test_shows_overdue_is_false_when_mark_overdue_is_off():
    now = DUE + timedelta(days=1)

    assert (
        shows_overdue(_resolved(DUE), _policy(mark_overdue=False), False, now) is False
    )


def test_shows_overdue_is_false_without_a_deadline():
    assert shows_overdue(NO_DEADLINE, _policy(), False, DUE) is False


def test_access_end_instant_is_the_time_limit_when_the_grace_window_is_zero():
    policy = _policy(end_course_access=True)

    assert access_end_instant(_resolved(DUE), policy) == DUE


def test_access_end_instant_adds_the_grace_window():
    policy = _policy(end_course_access=True, grace_window=timedelta(days=2))

    assert access_end_instant(_resolved(DUE), policy) == DUE + timedelta(days=2)


def test_access_end_instant_is_none_when_ending_access_is_off():
    assert access_end_instant(_resolved(DUE), _policy()) is None


def test_access_end_instant_is_none_without_a_time_limit():
    policy = _policy(end_course_access=True)

    assert access_end_instant(NO_DEADLINE, policy) is None
