from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from freedom_ls.deadlines.consequences import (
    access_end_instant,
    close_instant,
    has_access_ended,
    is_closed,
    shows_overdue,
)
from freedom_ls.deadlines.models import AfterAccessEnded
from freedom_ls.deadlines.policy import ResolvedDeadlinePolicy
from freedom_ls.deadlines.resolver import NO_DEADLINE, DeadlineSource, ResolvedDeadline

DUE = datetime(2026, 3, 20, 12, 0, tzinfo=UTC)


def _policy(
    *,
    mark_overdue: bool = True,
    close_items: bool = False,
    end_course_access: bool = False,
    grace_window: timedelta = timedelta(0),
) -> ResolvedDeadlinePolicy:
    return ResolvedDeadlinePolicy(
        mark_overdue=mark_overdue,
        close_items=close_items,
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


def test_close_instant_is_the_due_instant_plus_the_grace_window():
    policy = _policy(close_items=True, grace_window=timedelta(hours=2))

    assert close_instant(_resolved(DUE), policy) == DUE + timedelta(hours=2)


def test_close_instant_is_the_due_instant_when_the_grace_window_is_zero():
    assert close_instant(_resolved(DUE), _policy(close_items=True)) == DUE


def test_close_instant_is_none_without_a_due_instant():
    assert close_instant(_resolved(None), _policy(close_items=True)) is None


def test_close_instant_is_none_when_the_policy_does_not_close_items():
    assert close_instant(_resolved(DUE), _policy(close_items=False)) is None


@pytest.mark.parametrize("grace", [timedelta(0), timedelta(hours=2)])
@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        (timedelta(seconds=-1), False),
        (timedelta(0), False),
        (timedelta(seconds=1), True),
    ],
)
def test_is_closed_turns_on_after_the_close_instant(grace, offset, expected):
    policy = _policy(close_items=True, grace_window=grace)

    assert is_closed(_resolved(DUE), policy, False, DUE + grace + offset) is expected


def test_is_closed_is_false_for_a_completed_item():
    now = DUE + timedelta(days=1)

    assert is_closed(_resolved(DUE), _policy(close_items=True), True, now) is False


def test_is_closed_is_false_without_a_due_instant():
    now = DUE + timedelta(days=1)

    assert is_closed(_resolved(None), _policy(close_items=True), False, now) is False


def test_is_closed_is_false_when_the_policy_does_not_close_items():
    now = DUE + timedelta(days=1)

    assert is_closed(_resolved(DUE), _policy(close_items=False), False, now) is False


@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        (timedelta(seconds=-1), False),
        (timedelta(0), False),
        (timedelta(seconds=1), True),
    ],
)
def test_has_access_ended_turns_on_after_the_time_limit_plus_grace(offset, expected):
    grace = timedelta(days=2)
    policy = _policy(end_course_access=True, grace_window=grace)

    assert has_access_ended(_resolved(DUE), policy, DUE + grace + offset) is expected


def test_has_access_ended_is_false_when_the_policy_does_not_end_access():
    assert has_access_ended(_resolved(DUE), _policy(), DUE + timedelta(days=9)) is False


def test_has_access_ended_is_false_without_a_time_limit():
    policy = _policy(end_course_access=True)

    assert has_access_ended(NO_DEADLINE, policy, DUE + timedelta(days=9)) is False
