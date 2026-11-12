from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from freedom_ls.deadlines.models import CoursePause
from freedom_ls.deadlines.shifts import (
    ShiftSources,
    paused_days,
    shift_for_collection_item,
    shift_for_time_limit,
)

AMSTERDAM = ZoneInfo("Europe/Amsterdam")
START = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)
NOW = datetime(2026, 3, 20, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("elapsed", "expected"),
    [
        pytest.param(timedelta(0), 0, id="same-instant"),
        pytest.param(timedelta(seconds=1), 1, id="one-second"),
        pytest.param(timedelta(hours=24), 1, id="exactly-a-day"),
        pytest.param(timedelta(hours=24, seconds=1), 2, id="a-second-more"),
        pytest.param(timedelta(days=3), 3, id="whole-days"),
    ],
)
def test_paused_days_rounds_elapsed_time_up(elapsed: timedelta, expected: int):
    assert paused_days(START, START + elapsed) == expected


@pytest.mark.parametrize(
    ("end", "expected"),
    [
        pytest.param(datetime(2026, 3, 29, 12, 0, tzinfo=AMSTERDAM), 1, id="23-hours"),
        pytest.param(datetime(2026, 3, 29, 13, 0, tzinfo=AMSTERDAM), 1, id="24-hours"),
        pytest.param(datetime(2026, 3, 29, 14, 0, tzinfo=AMSTERDAM), 2, id="25-hours"),
    ],
)
def test_paused_days_across_a_dst_change_follows_elapsed_time(
    end: datetime, expected: int
):
    start = datetime(2026, 3, 28, 12, 0, tzinfo=AMSTERDAM)

    assert paused_days(start, end) == expected


def test_paused_days_is_zero_when_the_end_precedes_the_start():
    assert paused_days(START, START - timedelta(hours=1)) == 0


def _pause(started_at: datetime, ended_at: datetime | None) -> CoursePause:
    return CoursePause(started_at=started_at, ended_at=ended_at)


def test_the_time_limit_shift_sums_every_pause():
    sources = ShiftSources(
        pauses=[
            _pause(START, START + timedelta(days=2)),
            _pause(START + timedelta(days=5), START + timedelta(days=8)),
        ],
        completed_at={},
    )

    assert shift_for_time_limit(sources, NOW, AMSTERDAM) == 5


def test_an_item_with_no_completion_takes_every_pause():
    sources = ShiftSources(
        pauses=[_pause(START, START + timedelta(days=2))], completed_at={}
    )

    assert shift_for_collection_item(sources, uuid4(), NOW, AMSTERDAM) == 2


def test_an_item_completed_before_a_pause_began_is_not_moved_by_it():
    item_id = uuid4()
    sources = ShiftSources(
        pauses=[_pause(START, START + timedelta(days=2))],
        completed_at={item_id: START - timedelta(hours=1)},
    )

    assert shift_for_collection_item(sources, item_id, NOW, AMSTERDAM) == 0


def test_an_item_is_moved_only_by_pauses_that_began_before_it_was_completed():
    item_id = uuid4()
    sources = ShiftSources(
        pauses=[
            _pause(START, START + timedelta(days=2)),
            _pause(START + timedelta(days=6), START + timedelta(days=9)),
        ],
        completed_at={item_id: START + timedelta(days=4)},
    )

    assert shift_for_collection_item(sources, item_id, NOW, AMSTERDAM) == 2
