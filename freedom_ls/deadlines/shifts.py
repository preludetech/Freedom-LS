"""Whole-day shifts a pause moves a deadline by. Pure: no model is imported at runtime."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from freedom_ls.deadlines.models import CoursePause

SECONDS_PER_DAY = 86_400


def paused_days(started_at: datetime, end_at: datetime) -> int:
    """Whole days between two instants, rounded up: a pause of one second costs the learner
    a day of calendar, so it gives a day back. Zero only when nothing elapsed."""
    # Two datetimes sharing a zone subtract by wall clock; UTC makes it elapsed time.
    seconds = (end_at.astimezone(UTC) - started_at.astimezone(UTC)).total_seconds()
    return max(0, math.ceil(seconds / SECONDS_PER_DAY))


@dataclass(frozen=True)
class ShiftSources:
    """What moves one record's deadlines."""

    pauses: Sequence[CoursePause]
    # Collection item id -> the instant the item was completed.
    completed_at: Mapping[UUID, datetime]


def shift_for_time_limit(sources: ShiftSources, now: datetime, tz: ZoneInfo) -> int:
    """The time limit is unmet for as long as the course is, so every pause moves it."""
    return sum(pause.paused_days(now, tz) for pause in sources.pauses)


def shift_for_collection_item(
    sources: ShiftSources, collection_item_id: UUID, now: datetime, tz: ZoneInfo
) -> int:
    done = sources.completed_at.get(collection_item_id)
    # A pause that began after the item was met leaves its date alone.
    return sum(
        pause.paused_days(now, tz)
        for pause in sources.pauses
        if done is None or pause.started_at <= done
    )
