"""Per-row deadline reads for the admin: one override row at a time, so plain queries."""

from __future__ import annotations

from freedom_ls.deadlines.models import (
    CohortDeadlineOverride,
    LearnerDeadlineOverride,
)
from freedom_ls.deadlines.resolver import (
    DeadlineLayer,
    DeadlineSource,
    DeadlineValue,
    time_limit_value,
)


def content_default_for(
    row: CohortDeadlineOverride | LearnerDeadlineOverride,
) -> DeadlineValue | None:
    """What the content says for the row's item, or the course time limit for a time-limit row."""
    item = row.collection_item
    if item is not None:
        return DeadlineValue.from_columns(
            item.due_date, item.due_time, item.due_days_after_registration
        )
    course = row.course
    return time_limit_value(course.time_limit_days) if course is not None else None


def layers_beneath(
    row: CohortDeadlineOverride | LearnerDeadlineOverride,
) -> list[DeadlineLayer]:
    """The layers under this row, most specific first: the cohort row for a learner row whose
    record came through a cohort registration, then the content default."""
    layers: list[DeadlineLayer] = []
    if isinstance(row, LearnerDeadlineOverride):
        cohort_registration_id = row.course_progress.cohort_registration_id
        if cohort_registration_id is not None:
            cohort_row: CohortDeadlineOverride | None = (
                CohortDeadlineOverride.objects.filter(
                    cohort_registration_id=cohort_registration_id,
                    collection_item_id=row.collection_item_id,
                ).first()
            )
            if cohort_row is not None:
                layers.append(
                    DeadlineLayer(
                        DeadlineSource.COHORT_REGISTRATION, cohort_row.value()
                    )
                )
    layers.append(DeadlineLayer(DeadlineSource.CONTENT, content_default_for(row)))
    return layers


def canonical_beneath(
    row: CohortDeadlineOverride | LearnerDeadlineOverride,
) -> str:
    """The string replaced_value stores: the first value beneath, or '' when there is none."""
    for layer in layers_beneath(row):
        if layer.value is not None:
            return layer.value.canonical()
    return ""
