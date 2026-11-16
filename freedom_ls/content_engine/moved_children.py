"""The children a load moved from one collection item to another, and the course placement
due dates that follow them.

A sync never removes the row a moved child left behind, so anything pointing at that row
would otherwise stop applying.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from django.contrib.contenttypes.models import ContentType as DjangoContentType
from django.contrib.sites.models import Site

from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CoursePart,
    CoursePartChildDueDate,
)


@dataclass(frozen=True)
class MovedChild:
    """In `course`, the child of `stale` now sits on `new_row`."""

    course: Course
    stale: ContentCollectionItem
    new_row: ContentCollectionItem


# (child type id, child id): the content a collection item holds.
_ChildKey = tuple[int, UUID]


def moved_children(
    site: Site,
    written: list[ContentCollectionItem],
    loaded_collections: set[tuple[int, UUID]],
) -> list[MovedChild]:
    """Every unambiguous move among the rows a load wrote.

    `loaded_collections` holds the (collection type id, collection id) of every course and
    part the load saved. Only a row in one of those can have been left behind: the load
    wrote every child they list, so a row there it did not write is a child they no longer
    list. A row in a collection outside the load may be a placement made on purpose, which
    the load cannot tell apart from a move, so it is never taken to be one.

    Every written row is looked at, not only the created ones: a child moved back to where
    it came from lands on the row it left, which the load updates rather than creates. A
    move is exactly one left-behind row for the same child in the same course; a child with
    two is left for a person. A part placed in several courses is looked at in each of them.
    """
    written_ids = {row.pk for row in written}
    courses = _CoursesOfCollections(site)
    left_behind_by_course: dict[UUID, dict[_ChildKey, list[ContentCollectionItem]]] = {}
    moves: list[MovedChild] = []
    for new_row in written:
        for course in courses.placing(new_row):
            if course.pk not in left_behind_by_course:
                left_behind_by_course[course.pk] = _left_behind(
                    course, site, written_ids, loaded_collections
                )
            stale = left_behind_by_course[course.pk].get(
                (new_row.child_type_id, new_row.child_id), []
            )
            if len(stale) == 1:
                moves.append(MovedChild(course, stale[0], new_row))
    return moves


def _left_behind(
    course: Course,
    site: Site,
    written_ids: set[UUID],
    loaded_collections: set[tuple[int, UUID]],
) -> dict[_ChildKey, list[ContentCollectionItem]]:
    """The course's rows the load left behind, by the child they hold."""
    by_child: dict[_ChildKey, list[ContentCollectionItem]] = defaultdict(list)
    for row in course.viewable_collection_items():
        if (
            row.pk not in written_ids
            and row.site_id == site.pk
            and (row.collection_type_id, row.collection_id) in loaded_collections
        ):
            by_child[(row.child_type_id, row.child_id)].append(row)
    return by_child


def carry_placement_due_dates(site: Site, moves: list[MovedChild]) -> None:
    """Move the due date each course gives a moved child to the child's new row.

    When a child moves to another part and the course is not in the load, the course's
    placement due dates are not reconciled. A carried date is keyed by the course's
    placement of the new part, the part the new row sits in. A course reads one value per
    row whichever of its part placements gives it, so a course that already dates the new
    row keeps that date and leaves the stale row's alone. Only the course's own placements
    are moved: a part in two courses has a date from each.

    Three queries however many children moved.
    """
    part_type = DjangoContentType.objects.get_for_model(CoursePart)
    part_moves = [m for m in moves if m.new_row.collection_type_id == part_type.pk]
    if not part_moves:
        return
    course_type = DjangoContentType.objects.get_for_model(Course)
    course_ids = {move.course.pk for move in part_moves}
    placements = {
        (placement.collection_id, placement.child_id): placement
        for placement in ContentCollectionItem._base_manager.filter(
            site=site,
            collection_type=course_type,
            collection_id__in=course_ids,
            child_type=part_type,
            child_id__in={move.new_row.collection_id for move in part_moves},
        )
    }
    dates_by_course_row: dict[tuple[UUID, UUID], list[CoursePartChildDueDate]] = (
        defaultdict(list)
    )
    for date in (
        CoursePartChildDueDate._base_manager.filter(
            site=site,
            part_collection_item__collection_type=course_type,
            part_collection_item__collection_id__in=course_ids,
            collection_item__in=[
                row.pk for move in part_moves for row in (move.stale, move.new_row)
            ],
        )
        .select_related("part_collection_item")
        .order_by("pk")
    ):
        key = (date.part_collection_item.collection_id, date.collection_item_id)
        dates_by_course_row[key].append(date)

    carried: list[CoursePartChildDueDate] = []
    for move in part_moves:
        if (move.course.pk, move.new_row.pk) in dates_by_course_row:
            continue
        stale_dates = dates_by_course_row.get((move.course.pk, move.stale.pk))
        if not stale_dates:
            continue
        # A course that placed the old part twice dated the child twice; the new part's
        # placement takes one value per row, so the first is carried.
        date = stale_dates[0]
        date.part_collection_item = placements[
            (move.course.pk, move.new_row.collection_id)
        ]
        date.collection_item = move.new_row
        carried.append(date)
    CoursePartChildDueDate._base_manager.bulk_update(
        carried, ["part_collection_item", "collection_item"]
    )


class _CoursesOfCollections:
    """The courses each collection sits in, read once per collection for one load.

    Read through _base_manager with the load's site, because a load runs with no request; a
    fresh Course instance per load, so the memoised item tree is this load's.
    """

    def __init__(self, site: Site) -> None:
        self.site = site
        self.course_type = DjangoContentType.objects.get_for_model(Course)
        self.part_type = DjangoContentType.objects.get_for_model(CoursePart)
        self._courses: dict[tuple[int, UUID], list[Course]] = {}

    def placing(self, row: ContentCollectionItem) -> list[Course]:
        """The courses a row sits in: its collection when that is a course, else every course
        that places its part."""
        key = (row.collection_type_id, row.collection_id)
        if key not in self._courses:
            self._courses[key] = self._read(row)
        return self._courses[key]

    def _read(self, row: ContentCollectionItem) -> list[Course]:
        if row.collection_type_id == self.course_type.pk:
            course_ids = [row.collection_id]
        elif row.collection_type_id == self.part_type.pk:
            course_ids = list(
                ContentCollectionItem._base_manager.filter(
                    site=self.site,
                    collection_type=self.course_type,
                    child_type=self.part_type,
                    child_id=row.collection_id,
                ).values_list("collection_id", flat=True)
            )
        else:
            return []
        return list(
            Course._base_manager.filter(site=self.site, pk__in=course_ids).order_by(
                "pk"
            )
        )
