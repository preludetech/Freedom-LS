from __future__ import annotations

from datetime import datetime, timedelta


def offset_from(now: datetime, delta: timedelta | None) -> datetime | None:
    return None if delta is None else now + delta
