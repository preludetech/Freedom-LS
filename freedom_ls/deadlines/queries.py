"""Per-row deadline reads for the admin: one override row at a time, so plain queries."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from freedom_ls.content_engine.models import Course
from freedom_ls.deadlines.models import (
    CohortDeadlineOverride,
    LearnerDeadlineOverride,
)
from freedom_ls.deadlines.resolver import (
    DeadlineLayer,
    DeadlineSource,
    DeadlineValue,
    LayerRows,
    content_defaults_for_course,
    content_layer_value,
    time_limit_value,
)

ContentDefaults = Mapping[UUID, DeadlineValue | None]


def content_defaults_for(course: Course) -> ContentDefaults:
    """The content default of every viewable row in the course, keyed by row id, read the
    way the resolver reads it. A few queries for a page of rows."""
    return content_defaults_for_course(course.pk)


def content_default_for(
    row: CohortDeadlineOverride | LearnerDeadlineOverride,
    content_defaults: ContentDefaults | None = None,
) -> DeadlineValue | None:
    """What the content says for the row's item in the row's course, or the course time limit
    for a time-limit row. A row whose item is no longer reachable in the course falls back to
    the item's own value. `content_defaults` stands in for the course read when a caller has
    many rows under one course and fetched them at once."""
    item = row.collection_item
    course = row.course
    if item is None:
        return time_limit_value(course.time_limit_days) if course is not None else None
    if course is not None:
        values = (
            content_defaults
            if content_defaults is not None
            else content_defaults_for(course)
        )
        return values[item.pk] if item.pk in values else content_layer_value(item)
    return content_layer_value(item)


def layers_beneath(
    row: CohortDeadlineOverride | LearnerDeadlineOverride,
    cohort_rows: LayerRows | None = None,
    content_defaults: ContentDefaults | None = None,
) -> list[DeadlineLayer]:
    """The layers under this row, most specific first: the cohort row for a learner row whose
    record came through a cohort registration, then the content default.

    `cohort_rows`, keyed by (cohort registration id, collection item id), stands in for the
    cohort row query when a caller has many rows under one record and fetched them at once;
    `content_defaults` does the same for the course's content defaults."""
    layers: list[DeadlineLayer] = []
    if isinstance(row, LearnerDeadlineOverride):
        cohort_registration_id = row.course_progress.cohort_registration_id
        if cohort_registration_id is not None:
            cohort_row = (
                cohort_rows.get((cohort_registration_id, row.collection_item_id))
                if cohort_rows is not None
                else CohortDeadlineOverride.objects.filter(
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
    layers.append(
        DeadlineLayer(
            DeadlineSource.CONTENT, content_default_for(row, content_defaults)
        )
    )
    return layers


def canonical_beneath(
    row: CohortDeadlineOverride | LearnerDeadlineOverride,
    cohort_rows: LayerRows | None = None,
    content_defaults: ContentDefaults | None = None,
) -> str:
    """The string replaced_value stores: the first value beneath, or '' when there is none."""
    for layer in layers_beneath(row, cohort_rows, content_defaults):
        if layer.value is not None:
            return layer.value.canonical()
    return ""
