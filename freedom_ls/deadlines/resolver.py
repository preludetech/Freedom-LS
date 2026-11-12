from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, NamedTuple, Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CoursePart,
    CoursePartChildDueDate,
)
from freedom_ls.deadlines.models import (
    CohortDeadlineOverride,
    DeadlineKind,
    LearnerDeadlineOverride,
)
from freedom_ls.deadlines.shifts import (
    ShiftSources,
    shift_for_collection_item,
    shift_for_time_limit,
)
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.site_aware_models.time_zones import site_time_zone

if TYPE_CHECKING:
    from freedom_ls.deadlines.models import CoursePause


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
        no_due_date: bool,
    ) -> DeadlineValue | None:
        """The value four nullable columns express, or None when they hold no deadline.
        no_due_date is the content saying there is none, which is a value."""
        if no_due_date:
            return cls(DeadlineKind.NONE)
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


@dataclass(frozen=True)
class ResolvedDeadline:
    due_at: datetime | None
    source: DeadlineSource | None
    # Whole days the pauses moved `due_at` forward.
    shift_days: int = 0


NO_DEADLINE = ResolvedDeadline(due_at=None, source=None)


def due_instant(
    value: DeadlineValue,
    registration_date: date,
    tz: ZoneInfo,
    shift_days: int = 0,
) -> datetime | None:
    """The instant a value falls due for a learner registered on registration_date.

    Relative offsets are added to the local date, not to an instant, so a DST change between
    registration and the due day still lands on the local end of day. A value without a time
    is due at the last microsecond of its day. `shift_days` is added to the local date the same
    way, so a shift keeps the time of day across a DST change."""
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
    day += timedelta(days=shift_days)
    at = value.due_time if value.due_time is not None else time.max
    return datetime.combine(day, at, tzinfo=tz)


def resolve_deadline(
    layers: Sequence[DeadlineLayer],
    registration_date: date,
    tz: ZoneInfo,
    shift_days: int = 0,
) -> ResolvedDeadline:
    """Most specific layer first; the first layer holding a value wins outright."""
    for layer in layers:
        if layer.value is not None:
            return ResolvedDeadline(
                due_at=due_instant(layer.value, registration_date, tz, shift_days),
                source=layer.source,
                shift_days=(shift_days if layer.value.kind != DeadlineKind.NONE else 0),
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
    # The site zone every instant above was built in, kept so a reader of these
    # deadlines can ask "is that today?" without a second zone lookup.
    zone: ZoneInfo
    # The record's open pause, when it has one.
    pause: CoursePause | None = None


class DeadlineOverrideRow(Protocol):
    """What the layer builder reads from a deadline override row."""

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


def content_layer_value(
    row: ContentCollectionItem | CoursePartChildDueDate,
) -> DeadlineValue | None:
    """The value a content row's four columns express."""
    return DeadlineValue.from_columns(
        row.due_date, row.due_time, row.due_days_after_registration, row.no_due_date
    )


def _defaults_by_course(course_ids: set[UUID]) -> dict[UUID, _CourseDefaults]:
    """Four queries whatever the number of courses or rows: the course-level rows, the
    part-level rows beneath them, the values the courses' part placements give those rows,
    and the courses' time limits. Rows whose child is a part are containers, not items, so
    they carry no value. A part placed in several of the courses has its rows in each of
    them, each with that course's placement value when it sets one."""
    course_type = ContentType.objects.get_for_model(Course)
    part_type = ContentType.objects.get_for_model(CoursePart)
    top_rows = list(
        ContentCollectionItem.objects.filter(
            collection_type=course_type, collection_id__in=course_ids
        )
    )
    courses_of_part: dict[UUID, list[UUID]] = defaultdict(list)
    for row in top_rows:
        if row.child_type_id == part_type.pk:
            courses_of_part[row.child_id].append(row.collection_id)
    part_rows = list(
        ContentCollectionItem.objects.filter(
            collection_type=part_type, collection_id__in=courses_of_part
        )
    )
    # The course each part placement belongs to, so a value keyed by the placement is
    # credited to that course alone.
    course_of_part_placement = {
        row.pk: row.collection_id
        for row in top_rows
        if row.child_type_id == part_type.pk
    }
    placement_values: dict[tuple[UUID, UUID], DeadlineValue | None] = {}
    for placement_value in CoursePartChildDueDate.objects.filter(
        part_collection_item_id__in=course_of_part_placement.keys()
    ):
        course_id = course_of_part_placement[placement_value.part_collection_item_id]
        placement_values[(course_id, placement_value.collection_item_id)] = (
            content_layer_value(placement_value)
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
        placed_in = (
            [row.collection_id]
            if row.collection_type_id == course_type.pk
            else courses_of_part[row.collection_id]
        )
        value = content_layer_value(row)
        for course_id in placed_in:
            defaults[course_id].items[row.pk] = placement_values.get(
                (course_id, row.pk), value
            )
    return defaults


def _layer(source: DeadlineSource, row: DeadlineOverrideRow | None) -> DeadlineLayer:
    return DeadlineLayer(source, row.value() if row is not None else None)


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
        DeadlineLayer(DeadlineSource.CONTENT, content),
    ]


def content_defaults_for_course(course_id: UUID) -> Mapping[UUID, DeadlineValue | None]:
    """What the content says for every viewable row in one course, keyed by row id: the
    row's own value, or the value the course's placement of the row's part gives it. The
    one reading of a content default, shared with the admin so it never drifts from what
    a learner is resolved."""
    return _defaults_by_course({course_id})[course_id].items


def course_deadlines(
    course_progress: CourseProgress,
    *,
    now: datetime | None = None,
    items: bool = True,
    pauses: Mapping[UUID, list[CoursePause]] | None = None,
) -> CourseDeadlines:
    return course_deadlines_for([course_progress], now=now, items=items, pauses=pauses)[
        course_progress.pk
    ]


def course_deadlines_for(
    course_progress_records: Iterable[CourseProgress],
    *,
    now: datetime | None = None,
    items: bool = True,
    pauses: Mapping[UUID, list[CoursePause]] | None = None,
) -> dict[UUID, CourseDeadlines]:
    """Every record's resolved deadlines, keyed by record id.

    A fixed number of queries whatever the number of records or collection items. The site
    zone is read once; every record a request hands in belongs to the request's site.

    `now` is resolved once and decides which pauses are open. `pauses` is what a caller
    already read with `pauses_for`. With `items=False` the per-item deadlines and the reads
    that only they need are skipped, and `items` comes back empty."""
    from freedom_ls.deadlines.queries import open_pauses_for, pauses_for
    from freedom_ls.learner_progress.queries import completion_instants

    records = list(course_progress_records)
    if not records:
        return {}
    now = now if now is not None else timezone.now()
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

    if pauses is None:
        pauses = pauses_for(records)
    open_by_record = open_pauses_for(records, now, pauses)
    paused_ids = [record.pk for record in records if pauses.get(record.pk)]
    # Only a record with a pause has anything to shift, so the common page pays no read.
    completed = completion_instants(paused_ids) if items and paused_ids else {}

    result: dict[UUID, CourseDeadlines] = {}
    for record in records:
        registered_on = registration_date_of(record, tz)
        course_defaults = defaults[record.course_id]
        sources = ShiftSources(
            pauses=pauses.get(record.pk, []),
            completed_at={
                item_id: instant
                for (progress_id, item_id), instant in completed.items()
                if progress_id == record.pk
            },
        )
        resolved_items = (
            {
                item_id: resolve_deadline(
                    _layers(record, item_id, content, cohort_rows, learner_rows),
                    registered_on,
                    tz,
                    shift_for_collection_item(sources, item_id, now, tz),
                )
                for item_id, content in course_defaults.items.items()
            }
            if items
            else {}
        )
        time_limit = resolve_deadline(
            _layers(
                record, None, course_defaults.time_limit, cohort_rows, learner_rows
            ),
            registered_on,
            tz,
            shift_for_time_limit(sources, now, tz),
        )
        result[record.pk] = CourseDeadlines(
            items=resolved_items,
            time_limit=time_limit,
            zone=tz,
            pause=open_by_record.get(record.pk),
        )
    return result
