from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest

from freedom_ls.deadlines.models import CoursePause, DeadlineExtension, ExtensionTarget
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
        extensions=[],
        completed_at={},
    )

    assert shift_for_time_limit(sources, NOW, AMSTERDAM) == 5


def test_an_item_with_no_completion_takes_every_pause():
    sources = ShiftSources(
        pauses=[_pause(START, START + timedelta(days=2))],
        extensions=[],
        completed_at={},
    )

    assert shift_for_collection_item(sources, uuid4(), NOW, AMSTERDAM) == 2


def test_an_item_completed_before_a_pause_began_is_not_moved_by_it():
    item_id = uuid4()
    sources = ShiftSources(
        pauses=[_pause(START, START + timedelta(days=2))],
        extensions=[],
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
        extensions=[],
        completed_at={item_id: START + timedelta(days=4)},
    )

    assert shift_for_collection_item(sources, item_id, NOW, AMSTERDAM) == 2


def _extension(
    target_kind: str,
    days: int,
    *,
    collection_item_id: UUID | None = None,
    created_at: datetime = START,
) -> DeadlineExtension:
    return DeadlineExtension(
        target_kind=target_kind,
        days=days,
        collection_item_id=collection_item_id,
        created_at=created_at,
    )


def test_extensions_on_one_item_sum():
    item_id = uuid4()
    sources = ShiftSources(
        pauses=[],
        extensions=[
            _extension(ExtensionTarget.COLLECTION_ITEM, 7, collection_item_id=item_id),
            _extension(ExtensionTarget.COLLECTION_ITEM, 5, collection_item_id=item_id),
        ],
        completed_at={},
    )

    assert shift_for_collection_item(sources, item_id, NOW, AMSTERDAM) == 12


def test_an_item_extension_leaves_other_items_alone():
    sources = ShiftSources(
        pauses=[],
        extensions=[
            _extension(ExtensionTarget.COLLECTION_ITEM, 7, collection_item_id=uuid4())
        ],
        completed_at={},
    )

    assert shift_for_collection_item(sources, uuid4(), NOW, AMSTERDAM) == 0


def test_an_item_extension_applies_after_the_item_was_completed():
    item_id = uuid4()
    sources = ShiftSources(
        pauses=[],
        extensions=[
            _extension(ExtensionTarget.COLLECTION_ITEM, 7, collection_item_id=item_id)
        ],
        completed_at={item_id: START - timedelta(days=1)},
    )

    assert shift_for_collection_item(sources, item_id, NOW, AMSTERDAM) == 7


def test_a_pause_and_an_extension_sum_for_an_item_and_only_the_pause_for_none_of_it():
    item_id = uuid4()
    sources = ShiftSources(
        pauses=[_pause(START, START + timedelta(days=2))],
        extensions=[
            _extension(ExtensionTarget.COLLECTION_ITEM, 7, collection_item_id=item_id)
        ],
        completed_at={},
    )

    assert shift_for_collection_item(sources, item_id, NOW, AMSTERDAM) == 9
    assert shift_for_time_limit(sources, NOW, AMSTERDAM) == 2


@pytest.mark.parametrize(
    ("created_at", "expected"),
    [
        pytest.param(START - timedelta(hours=1), 7, id="before-completion"),
        pytest.param(START + timedelta(hours=1), 0, id="after-completion"),
        pytest.param(START, 7, id="at-completion"),
    ],
)
def test_a_course_extension_skips_an_item_completed_before_it_was_made(
    created_at: datetime, expected: int
):
    item_id = uuid4()
    sources = ShiftSources(
        pauses=[],
        extensions=[_extension(ExtensionTarget.COURSE, 7, created_at=created_at)],
        completed_at={item_id: START},
    )

    assert shift_for_collection_item(sources, item_id, NOW, AMSTERDAM) == expected


def test_a_course_extension_moves_an_item_never_completed():
    sources = ShiftSources(
        pauses=[], extensions=[_extension(ExtensionTarget.COURSE, 7)], completed_at={}
    )

    assert shift_for_collection_item(sources, uuid4(), NOW, AMSTERDAM) == 7


@pytest.mark.parametrize(
    ("target_kind", "expected"),
    [
        pytest.param(ExtensionTarget.TIME_LIMIT, 7, id="time-limit"),
        pytest.param(ExtensionTarget.COURSE, 7, id="course"),
        pytest.param(ExtensionTarget.COLLECTION_ITEM, 0, id="collection-item"),
    ],
)
def test_the_time_limit_shift_counts_time_limit_and_course_extensions(
    target_kind: str, expected: int
):
    sources = ShiftSources(
        pauses=[],
        extensions=[_extension(target_kind, 7, collection_item_id=uuid4())],
        completed_at={},
    )

    assert shift_for_time_limit(sources, NOW, AMSTERDAM) == expected


def test_a_time_limit_extension_moves_no_item():
    sources = ShiftSources(
        pauses=[],
        extensions=[_extension(ExtensionTarget.TIME_LIMIT, 7)],
        completed_at={},
    )

    assert shift_for_collection_item(sources, uuid4(), NOW, AMSTERDAM) == 0
