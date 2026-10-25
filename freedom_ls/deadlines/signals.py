"""Signal receivers for the deadlines app.

Connected by `DeadlinesConfig.ready()`. A receiver in a module nothing imports
is never connected, and fails silently rather than loudly.
"""

from __future__ import annotations

from uuid import UUID

from django.contrib.contenttypes.models import ContentType as DjangoContentType
from django.contrib.sites.models import Site
from django.dispatch import receiver

from freedom_ls.content_engine.models import ContentCollectionItem, Course, CoursePart
from freedom_ls.content_engine.signals import collection_items_synced
from freedom_ls.deadlines.models import (
    CohortDeadlineOverride,
    LearnerDeadlineOverride,
    course_viewable_collection_items,
)


@receiver(collection_items_synced)
def carry_over_deadline_overrides(
    sender: type[ContentCollectionItem],
    site: Site,
    created: list[ContentCollectionItem],
    written: list[ContentCollectionItem],
    **kwargs: object,
) -> None:
    """Move deadline override rows from a child's stale collection item to the one a load just
    made.

    A sync never removes the row a moved child left behind, so the deadline overrides pointing
    at it would otherwise stop applying. Only the unambiguous case moves: exactly one other row
    for the same child in the same course that this load did not write. A file with two
    collection items on purpose has both rows written, and a child with two stale rows is left
    for a person. A part placed in several courses is looked at in each of them.

    A first load creates every row, so the courses and their item trees are read once per load
    rather than once per created row.
    """
    written_ids = {row.pk for row in written}
    courses = _CoursesOfCollections(site)
    items_by_course: dict[UUID, list[ContentCollectionItem]] = {}
    for new_row in created:
        for course in courses.placing(new_row):
            if course.pk not in items_by_course:
                items_by_course[course.pk] = course_viewable_collection_items(course)
            stale = [
                row
                for row in items_by_course[course.pk]
                if row.pk != new_row.pk
                and row.pk not in written_ids
                and row.site_id == site.pk
                and (row.child_type_id, row.child_id)
                == (new_row.child_type_id, new_row.child_id)
            ]
            if len(stale) != 1:
                continue
            for model in (CohortDeadlineOverride, LearnerDeadlineOverride):
                model._base_manager.filter(site=site, collection_item=stale[0]).update(
                    collection_item=new_row
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
