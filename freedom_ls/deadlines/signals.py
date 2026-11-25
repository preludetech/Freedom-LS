"""Signal receivers for the deadlines app.

Connected by `DeadlinesConfig.ready()`. A receiver in a module nothing imports
is never connected, and fails silently rather than loudly.
"""

from __future__ import annotations

from collections import Counter

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.dispatch import receiver

from freedom_ls.content_engine.models import ContentCollectionItem, Course, CoursePart
from freedom_ls.content_engine.moved_children import MovedChild
from freedom_ls.content_engine.signals import (
    collection_items_synced,
    part_placement_removed,
)
from freedom_ls.deadlines.models import (
    CohortDeadlineOverride,
    DeadlineExtension,
    LearnerDeadlineOverride,
)


@receiver(collection_items_synced)
def carry_over_deadline_overrides(
    sender: type[ContentCollectionItem],
    site: Site,
    moved: list[MovedChild],
    **kwargs: object,
) -> None:
    """Move deadline override rows from a moved child's stale collection item to the one the
    load wrote.

    A sync never removes the row a moved child left behind, so the overrides pointing at it
    would otherwise stop applying. A registration or record that already has an override on
    the new row keeps it; its row on the stale item stays where it is rather than clash.
    """
    for move in moved:
        for model, parent, unique_per_parent in _CARRIED_PARENTS:
            stale_rows = model._base_manager.filter(
                site=site, collection_item=move.stale
            )
            if unique_per_parent:
                already_on_new_row = model._base_manager.filter(
                    collection_item=move.new_row
                ).values(parent)
                stale_rows = stale_rows.exclude(**{f"{parent}__in": already_on_new_row})
            stale_rows.update(collection_item=move.new_row)


# Each model whose rows follow a moved child, with the field that names whose row it is,
# which the unique constraints pair with the collection item, and whether the model holds at
# most one row per parent and item. A model that does not (stacked extensions) never clashes,
# so every stale row moves.
_CARRIED_PARENTS: tuple[
    tuple[
        type[CohortDeadlineOverride]
        | type[LearnerDeadlineOverride]
        | type[DeadlineExtension],
        str,
        bool,
    ],
    ...,
] = (
    (CohortDeadlineOverride, "cohort_registration", True),
    (LearnerDeadlineOverride, "course_progress", True),
    (DeadlineExtension, "course_progress", False),
)


@receiver(part_placement_removed, dispatch_uid="deadlines.part_placement_removed")
def delete_deadlines_on_removed_part_topics(
    sender: type[ContentCollectionItem],
    site: Site,
    course: Course,
    part: CoursePart,
    **kwargs: object,
) -> Counter[str]:
    """Delete the course's overrides and extensions on the topics of a part it no longer
    places. Returns the rows deleted per model label, for content_save's report.

    The placement's own rows went with it in the cascade, but the part's topic rows
    belong to the part and stay, so this course's deadlines on them would otherwise
    linger on reference material, which has no deadline. A topic row the course still
    reaches some other way keeps its deadlines, retired or not.
    """
    part_items = ContentCollectionItem._base_manager.filter(
        site=site,
        collection_type=ContentType.objects.get_for_model(CoursePart),
        collection_id=part.id,
    ).exclude(
        # A fresh instance: Course memoizes its tree, and the caller's may predate the
        # removal.
        id__in=[
            item.id
            for item in Course._base_manager.get(
                pk=course.pk
            ).viewable_collection_items(include_retired=True)
        ]
    )
    deleted: Counter[str] = Counter()
    for rows in (
        CohortDeadlineOverride._base_manager.filter(
            site=site, cohort_registration__course=course
        ),
        LearnerDeadlineOverride._base_manager.filter(
            site=site, course_progress__course=course
        ),
        DeadlineExtension._base_manager.filter(
            site=site, course_progress__course=course
        ),
    ):
        _, per_model = rows.filter(collection_item__in=part_items).delete()
        deleted.update(per_model)
    return deleted
