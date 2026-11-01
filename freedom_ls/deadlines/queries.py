"""Per-row deadline reads for the admin: one override row at a time, so plain queries."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from django.contrib.contenttypes.models import ContentType

from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CoursePart,
    CoursePartChildDueDate,
)
from freedom_ls.deadlines.models import (
    CohortDeadlineOverride,
    LearnerDeadlineOverride,
)
from freedom_ls.deadlines.resolver import (
    DeadlineLayer,
    DeadlineSource,
    DeadlineValue,
    LayerRows,
    content_layer_value,
    time_limit_value,
)

PlacementValues = Mapping[UUID, DeadlineValue | None]


def placement_values_for(course: Course) -> PlacementValues:
    """Every value the course's part placements give the parts' children, keyed by the
    child's row id. One query for a page of rows."""
    course_type = ContentType.objects.get_for_model(Course)
    return {
        value.collection_item_id: content_layer_value(value)
        for value in CoursePartChildDueDate.objects.filter(
            part_collection_item__collection_type=course_type,
            part_collection_item__collection_id=course.pk,
        )
    }


def _sits_in_a_part(item: ContentCollectionItem) -> bool:
    return item.collection_type_id == ContentType.objects.get_for_model(CoursePart).pk


def content_default_for(
    row: CohortDeadlineOverride | LearnerDeadlineOverride,
    placement_values: PlacementValues | None = None,
) -> DeadlineValue | None:
    """What the content says for the row's item in the row's course, or the course time limit
    for a time-limit row. A part's row carries the part's value; the course's placement of the
    part replaces it when it sets one. `placement_values` stands in for that read when a
    caller has many rows under one course and fetched them at once."""
    item = row.collection_item
    course = row.course
    if item is None:
        return time_limit_value(course.time_limit_days) if course is not None else None
    if course is not None and _sits_in_a_part(item):
        values = (
            placement_values
            if placement_values is not None
            else placement_values_for(course)
        )
        return values[item.pk] if item.pk in values else content_layer_value(item)
    return content_layer_value(item)


def layers_beneath(
    row: CohortDeadlineOverride | LearnerDeadlineOverride,
    cohort_rows: LayerRows | None = None,
    placement_values: PlacementValues | None = None,
) -> list[DeadlineLayer]:
    """The layers under this row, most specific first: the cohort row for a learner row whose
    record came through a cohort registration, then the content default.

    `cohort_rows`, keyed by (cohort registration id, collection item id), stands in for the
    cohort row query when a caller has many rows under one record and fetched them at once;
    `placement_values` does the same for the part placement values."""
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
            DeadlineSource.CONTENT, content_default_for(row, placement_values)
        )
    )
    return layers


def canonical_beneath(
    row: CohortDeadlineOverride | LearnerDeadlineOverride,
    cohort_rows: LayerRows | None = None,
    placement_values: PlacementValues | None = None,
) -> str:
    """The string replaced_value stores: the first value beneath, or '' when there is none."""
    for layer in layers_beneath(row, cohort_rows, placement_values):
        if layer.value is not None:
            return layer.value.canonical()
    return ""
