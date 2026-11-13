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
    from freedom_ls.deadlines.models import CoursePause, DeadlineExtension

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
    extensions: Sequence[DeadlineExtension]
    # Collection item id -> the instant the item was completed.
    completed_at: Mapping[UUID, datetime]


def shift_for_time_limit(sources: ShiftSources, now: datetime, tz: ZoneInfo) -> int:
    """The time limit is unmet for as long as the course is, so every pause moves it, as
    does every extension aimed at the time limit or the whole course."""
    from freedom_ls.deadlines.models import ExtensionTarget

    return sum(pause.paused_days(now, tz) for pause in sources.pauses) + sum(
        extension.days
        for extension in sources.extensions
        if extension.target_kind in (ExtensionTarget.TIME_LIMIT, ExtensionTarget.COURSE)
    )


def shift_for_collection_item(
    sources: ShiftSources, collection_item_id: UUID, now: datetime, tz: ZoneInfo
) -> int:
    from freedom_ls.deadlines.models import ExtensionTarget

    done = sources.completed_at.get(collection_item_id)
    # A pause or whole-course extension that began after the item was met leaves its date
    # alone; an extension aimed at the item always applies.
    total = sum(
        pause.paused_days(now, tz)
        for pause in sources.pauses
        if done is None or pause.started_at <= done
    )
    for extension in sources.extensions:
        if extension.target_kind == ExtensionTarget.COLLECTION_ITEM:
            if extension.collection_item_id == collection_item_id:
                total += extension.days
        elif extension.target_kind == ExtensionTarget.COURSE and (
            done is None or extension.created_at <= done
        ):
            total += extension.days
    return total
