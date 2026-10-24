"""Per-row deadline reads for the admin: one override row at a time, so plain queries."""

from __future__ import annotations

from freedom_ls.deadlines.models import CohortDeadlineOverride
from freedom_ls.deadlines.resolver import (
    DeadlineLayer,
    DeadlineSource,
    DeadlineValue,
    time_limit_value,
)


def content_default_for(row: CohortDeadlineOverride) -> DeadlineValue | None:
    """What the content says for the row's item, or the course time limit for a time-limit row."""
    item = row.collection_item
    if item is not None:
        return DeadlineValue.from_columns(
            item.due_date, item.due_time, item.due_days_after_registration
        )
    course = row.course
    return time_limit_value(course.time_limit_days) if course is not None else None


def layers_beneath(row: CohortDeadlineOverride) -> list[DeadlineLayer]:
    """The layers under this row, most specific first. A cohort row sits directly on the
    content default."""
    return [DeadlineLayer(DeadlineSource.CONTENT, content_default_for(row), None)]


def canonical_beneath(row: CohortDeadlineOverride) -> str:
    """The string replaced_value stores: the first value beneath, or '' when there is none."""
    for layer in layers_beneath(row):
        if layer.value is not None:
            return layer.value.canonical()
    return ""
