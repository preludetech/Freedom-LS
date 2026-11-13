"""The children a load moved from one collection item to another, and the course placement
due dates that follow them.

A sync never removes the row a moved child left behind, so anything pointing at that row
would otherwise stop applying.
"""

from __future__ import annotations

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


def moved_children(
    site: Site, written: list[ContentCollectionItem]
) -> list[MovedChild]:
    """Every unambiguous move among the rows a load wrote.

    Every written row is looked at, not only the created ones: a child moved back to where
    it came from lands on the row it left, which the load updates rather than creates. A
    move is exactly one other row for the same child in the same course that this load did
    not write. A file with two collection items on purpose has both rows written, and a
    child with two stale rows is left for a person. A part placed in several courses is
    looked at in each of them.

    The courses and their item trees are read once per load rather than once per row.
    """
    written_ids = {row.pk for row in written}
    courses = _CoursesOfCollections(site)
    items_by_course: dict[UUID, list[ContentCollectionItem]] = {}
    moves: list[MovedChild] = []
    for new_row in written:
        for course in courses.placing(new_row):
            if course.pk not in items_by_course:
                items_by_course[course.pk] = course.viewable_collection_items()
            stale = [
                row
                for row in items_by_course[course.pk]
                if row.pk != new_row.pk
                and row.pk not in written_ids
                and row.site_id == site.pk
                and (row.child_type_id, row.child_id)
                == (new_row.child_type_id, new_row.child_id)
            ]
            if len(stale) == 1:
                moves.append(MovedChild(course, stale[0], new_row))
    return moves


def carry_placement_due_dates(site: Site, moves: list[MovedChild]) -> None:
    """Move the due date each course gives a moved child to the child's new row.

    When a child moves to another part and only that part's directory is reloaded, the
    course is not in the load, so its placement due dates are not reconciled. A course reads
    one value per row whichever of its part placements gives it, so a course that already
    dates the new row keeps that date and leaves the stale row's alone. Only the course's
    own placements are moved: a part in two courses has a date from each.
    """
    if not moves:
        return
    course_type = DjangoContentType.objects.get_for_model(Course)
    for move in moves:
        dates = CoursePartChildDueDate._base_manager.filter(
            site=site,
            part_collection_item__collection_type=course_type,
            part_collection_item__collection_id=move.course.pk,
        )
        if dates.filter(collection_item=move.new_row).exists():
            continue
        dates.filter(collection_item=move.stale).update(collection_item=move.new_row)


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
