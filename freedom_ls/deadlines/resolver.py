from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from typing import NamedTuple, Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from django.contrib.contenttypes.models import ContentType

from freedom_ls.content_engine.models import ContentCollectionItem, Course, CoursePart
from freedom_ls.deadlines.models import (
    CohortDeadlineOverride,
    DeadlineKind,
    LearnerDeadlineOverride,
)
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.site_aware_models.time_zones import site_time_zone


class DeadlineSource(StrEnum):
    CONTENT = "content"
    COHORT_REGISTRATION = "cohort_registration"
    LEARNER = "learner"


@dataclass(frozen=True)
class DeadlineValue:
    kind: DeadlineKind
    due_date: date | None = None
    due_time: time | None = None
    due_days_after_registration: int | None = None

    @classmethod
    def from_columns(
        cls,
        due_date: date | None,
        due_time: time | None,
        due_days_after_registration: int | None,
    ) -> DeadlineValue | None:
        """The value three nullable columns express, or None when they hold no deadline."""
        if due_date is not None:
            return cls(DeadlineKind.FIXED, due_date=due_date, due_time=due_time)
        if due_days_after_registration is not None:
            return cls(
                DeadlineKind.RELATIVE,
                due_time=due_time,
                due_days_after_registration=due_days_after_registration,
            )
        return None

    def canonical(self) -> str:
        """One string per distinct value, so a stored copy can be compared with a later read."""
        if self.kind == DeadlineKind.NONE:
            return "none"
        suffix = f"T{self.due_time:%H:%M}" if self.due_time is not None else ""
        if self.kind == DeadlineKind.FIXED:
            if self.due_date is None:
                raise ValueError("A fixed deadline carries a date.")
            return f"fixed:{self.due_date.isoformat()}{suffix}"
        return f"relative:{self.due_days_after_registration}{suffix}"


class DeadlineLayer(NamedTuple):
    source: DeadlineSource
    value: DeadlineValue | None
    replaced_value: str | None


@dataclass(frozen=True)
class ResolvedDeadline:
    due_at: datetime | None
    source: DeadlineSource | None
    default_changed: bool


NO_DEADLINE = ResolvedDeadline(due_at=None, source=None, default_changed=False)


def due_instant(
    value: DeadlineValue, registration_date: date, tz: ZoneInfo
) -> datetime | None:
    """The instant a value falls due for a learner registered on registration_date.

    Relative offsets are added to the local date, not to an instant, so a DST change between
    registration and the due day still lands on the local end of day. A value without a time
    is due at the last microsecond of its day."""
    if value.kind == DeadlineKind.NONE:
        return None
    if value.kind == DeadlineKind.FIXED:
        if value.due_date is None:
            raise ValueError("A fixed deadline carries a date.")
        day = value.due_date
    else:
        if value.due_days_after_registration is None:
            raise ValueError("A relative deadline carries a number of days.")
        day = registration_date + timedelta(days=value.due_days_after_registration)
    at = value.due_time if value.due_time is not None else time.max
    return datetime.combine(day, at, tzinfo=tz)


def resolve_deadline(
    layers: Sequence[DeadlineLayer], registration_date: date, tz: ZoneInfo
) -> ResolvedDeadline:
    """Most specific layer first; the first layer holding a value wins outright.

    default_changed compares the winning layer's stored copy of what it replaced with what
    sits beneath it now, so an admin can see that a content default moved under an override."""
    for position, layer in enumerate(layers):
        if layer.value is None:
            continue
        beneath = next(
            (
                lower.value
                for lower in layers[position + 1 :]
                if lower.value is not None
            ),
            None,
        )
        beneath_canonical = beneath.canonical() if beneath is not None else ""
        return ResolvedDeadline(
            due_at=due_instant(layer.value, registration_date, tz),
            source=layer.source,
            default_changed=layer.replaced_value is not None
            and layer.replaced_value != beneath_canonical,
        )
    return NO_DEADLINE


def is_overdue(resolved: ResolvedDeadline, completed: bool, now: datetime) -> bool:
    return resolved.due_at is not None and not completed and now > resolved.due_at


def registration_date_of(course_progress: CourseProgress, tz: ZoneInfo) -> date:
    """The date part of the record's creation, in the site's zone."""
    return course_progress.created_at.astimezone(tz).date()


@dataclass(frozen=True)
class CourseDeadlines:
    items: dict[UUID, ResolvedDeadline]
    time_limit: ResolvedDeadline


class DeadlineOverrideRow(Protocol):
    """What the layer builder reads from a deadline override row."""

    @property
    def replaced_value(self) -> str: ...

    def value(self) -> DeadlineValue | None: ...


LayerRows = Mapping[tuple[UUID, UUID | None], DeadlineOverrideRow]


@dataclass(frozen=True)
class _CourseDefaults:
    """What the content says for one course: a value per viewable row, and the time limit."""

    items: dict[UUID, DeadlineValue | None]
    time_limit: DeadlineValue | None


def time_limit_value(days: int | None) -> DeadlineValue | None:
    if days is None:
        return None
    return DeadlineValue(DeadlineKind.RELATIVE, due_days_after_registration=days)


def _defaults_by_course(course_ids: set[UUID]) -> dict[UUID, _CourseDefaults]:
    """Three queries whatever the number of courses or rows: the course-level rows, the
    part-level rows beneath them, and the courses' time limits. Rows whose child is a part are
    containers, not items, so they carry no value."""
    course_type = ContentType.objects.get_for_model(Course)
    part_type = ContentType.objects.get_for_model(CoursePart)
    top_rows = list(
        ContentCollectionItem.objects.filter(
            collection_type=course_type, collection_id__in=course_ids
        )
    )
    course_of_part = {
        row.child_id: row.collection_id
        for row in top_rows
        if row.child_type_id == part_type.pk
    }
    part_rows = list(
        ContentCollectionItem.objects.filter(
            collection_type=part_type, collection_id__in=course_of_part
        )
    )
    time_limit_days = dict(
        Course.objects.filter(pk__in=course_ids).values_list("pk", "time_limit_days")
    )

    defaults = {
        course_id: _CourseDefaults(
            items={}, time_limit=time_limit_value(time_limit_days.get(course_id))
        )
        for course_id in course_ids
    }
    for row in top_rows + part_rows:
        if row.child_type_id == part_type.pk:
            continue
        course_id = (
            row.collection_id
            if row.collection_type_id == course_type.pk
            else course_of_part[row.collection_id]
        )
        defaults[course_id].items[row.pk] = DeadlineValue.from_columns(
            row.due_date, row.due_time, row.due_days_after_registration
        )
    return defaults


def _layer(source: DeadlineSource, row: DeadlineOverrideRow | None) -> DeadlineLayer:
    if row is None:
        return DeadlineLayer(source, None, None)
    return DeadlineLayer(source, row.value(), row.replaced_value)


def _layers(
    record: CourseProgress,
    item_id: UUID | None,
    content: DeadlineValue | None,
    cohort_rows: LayerRows,
    learner_rows: LayerRows,
) -> list[DeadlineLayer]:
    cohort_row = (
        cohort_rows.get((record.cohort_registration_id, item_id))
        if record.cohort_registration_id
        else None
    )
    return [
        _layer(DeadlineSource.LEARNER, learner_rows.get((record.pk, item_id))),
        _layer(DeadlineSource.COHORT_REGISTRATION, cohort_row),
        DeadlineLayer(DeadlineSource.CONTENT, content, None),
    ]


def course_deadlines(course_progress: CourseProgress) -> CourseDeadlines:
    return course_deadlines_for([course_progress])[course_progress.pk]


def course_deadlines_for(
    course_progress_records: Iterable[CourseProgress],
) -> dict[UUID, CourseDeadlines]:
    """Every record's resolved deadlines, keyed by record id.

    A fixed number of queries whatever the number of records or collection items. The site
    zone is read once; every record a request hands in belongs to the request's site."""
    records = list(course_progress_records)
    if not records:
        return {}
    tz = site_time_zone(records[0].site)
    defaults = _defaults_by_course({record.course_id for record in records})
    cohort_rows: LayerRows = {
        (row.cohort_registration_id, row.collection_item_id): row
        for row in CohortDeadlineOverride.objects.filter(
            cohort_registration_id__in={
                record.cohort_registration_id
                for record in records
                if record.cohort_registration_id
            }
        )
    }
    learner_rows: LayerRows = {
        (row.course_progress_id, row.collection_item_id): row
        for row in LearnerDeadlineOverride.objects.filter(
            course_progress_id__in=[record.pk for record in records]
        )
    }

    result: dict[UUID, CourseDeadlines] = {}
    for record in records:
        registered_on = registration_date_of(record, tz)
        course_defaults = defaults[record.course_id]
        items = {
            item_id: resolve_deadline(
                _layers(record, item_id, content, cohort_rows, learner_rows),
                registered_on,
                tz,
            )
            for item_id, content in course_defaults.items.items()
        }
        time_limit = resolve_deadline(
            _layers(
                record, None, course_defaults.time_limit, cohort_rows, learner_rows
            ),
            registered_on,
            tz,
        )
        result[record.pk] = CourseDeadlines(items=items, time_limit=time_limit)
    return result
