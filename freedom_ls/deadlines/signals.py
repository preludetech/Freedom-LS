"""Signal receivers for the deadlines app.

Connected by `DeadlinesConfig.ready()`. A receiver in a module nothing imports
is never connected, and fails silently rather than loudly.
"""

from __future__ import annotations

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
    for a person.
    """
    written_ids = {row.pk for row in written}
    for new_row in created:
        course = _course_of_collection_item(new_row, site)
        if course is None:
            continue
        stale = [
            row
            for row in course_viewable_collection_items(course)
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


def _course_of_collection_item(row: ContentCollectionItem, site: Site) -> Course | None:
    """The course a row sits in: its collection when that is a course, else the course that
    places its part.

    Read through _base_manager with the load's site, because a load runs with no request; a
    fresh instance each time, so the memoised item tree is this load's.
    """
    course_type = DjangoContentType.objects.get_for_model(Course)
    part_type = DjangoContentType.objects.get_for_model(CoursePart)
    collection_id = row.collection_id
    if row.collection_type_id == part_type.pk:
        placement = (
            ContentCollectionItem._base_manager.filter(
                site=site,
                collection_type=course_type,
                child_type=part_type,
                child_id=collection_id,
            )
            .order_by("pk")
            .first()
        )
        if placement is None:
            return None
        collection_id = placement.collection_id
    elif row.collection_type_id != course_type.pk:
        return None
    return Course._base_manager.filter(site=site, pk=collection_id).first()
