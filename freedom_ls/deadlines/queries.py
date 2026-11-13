"""Per-row deadline reads for the admin: one override row at a time, so plain queries."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from freedom_ls.deadlines.models import (
    CohortDeadlineOverride,
    CoursePause,
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
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.site_aware_models.time_zones import site_time_zone

ContentDefaults = Mapping[UUID, DeadlineValue | None]


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
            else content_defaults_for_course(course.pk)
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


def pauses_for(records: Iterable[CourseProgress]) -> dict[UUID, list[CoursePause]]:
    """Every pause of the given records, open and ended, newest first, in one query.

    Read through the base manager with the records' sites, because the services and the
    housekeeping sweep run with no request to supply a site. Records with no pause are
    absent from the result."""
    records = list(records)
    by_record: dict[UUID, list[CoursePause]] = {}
    if not records:
        return by_record
    rows = CoursePause._base_manager.filter(
        site_id__in={record.site_id for record in records},
        course_progress_id__in=[record.pk for record in records],
    )
    for pause in rows:
        by_record.setdefault(pause.course_progress_id, []).append(pause)
    return by_record


def open_pauses_for(
    records: Iterable[CourseProgress],
    now: datetime,
    pauses: Mapping[UUID, list[CoursePause]] | None = None,
) -> dict[UUID, CoursePause]:
    """The open pause of each paused record, keyed by record id.

    `pauses` is what a caller already read with `pauses_for`, so the state costs no query."""
    records = list(records)
    if pauses is None:
        pauses = pauses_for(records)
    open_by_record: dict[UUID, CoursePause] = {}
    zones: dict[int, ZoneInfo] = {}
    for record in records:
        if record.site_id not in zones:
            zones[record.site_id] = site_time_zone(record.site)
        tz = zones[record.site_id]
        for pause in pauses.get(record.pk, []):
            if pause.is_open(now, tz):
                open_by_record[record.pk] = pause
                break
    return open_by_record


def open_pause(
    record: CourseProgress,
    now: datetime,
    pauses: Mapping[UUID, list[CoursePause]] | None = None,
) -> CoursePause | None:
    return open_pauses_for([record], now, pauses).get(record.pk)
