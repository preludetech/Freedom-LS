"""Signal receivers for the deadlines app.

Connected by `DeadlinesConfig.ready()`. A receiver in a module nothing imports
is never connected, and fails silently rather than loudly.
"""

from __future__ import annotations

from django.contrib.sites.models import Site
from django.dispatch import receiver

from freedom_ls.content_engine.models import ContentCollectionItem
from freedom_ls.content_engine.moved_children import MovedChild
from freedom_ls.content_engine.signals import collection_items_synced
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
