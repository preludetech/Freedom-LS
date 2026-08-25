from itertools import batched
from uuid import UUID

import djclick as click

from freedom_ls.learner_management.utils import calculate_course_progress_percentage
from freedom_ls.learner_progress.models import (
    CourseProgress,
    TopicProgress,
)
from freedom_ls.learner_progress.queries import (
    completed_form_item_ids_by_course_progress,
)

# Course progress records per batch. The command walks every record in the
# installation, and the completed-item lookups it needs are model instances, not
# id tuples — fetching them for every record at once is what makes this a
# memory-bound command instead of a scan.
RECORD_BATCH_SIZE = 500


@click.command()
def command() -> None:
    """Recalculate progress_percentage for all CourseProgress records.

    Useful for backfilling after the progress_percentage field was added,
    or after data migrations that may have left stale values.
    """
    all_course_progress = CourseProgress.objects.select_related("course").all()
    total = all_course_progress.count()

    if total == 0:
        click.echo("No CourseProgress records found.")
        return

    record_ids = list(CourseProgress.objects.values_list("pk", flat=True).iterator())

    updated = 0
    for batch in batched(record_ids, RECORD_BATCH_SIZE, strict=False):
        # Collection item ids from both sources, unioned per record: the
        # percentage counts placements, not the content behind them.
        completed_items: dict[UUID, set[UUID]] = {}
        for course_progress_id, collection_item_id in TopicProgress.objects.filter(
            course_progress_id__in=batch,
            complete_time__isnull=False,
            collection_item__isnull=False,
        ).values_list("course_progress_id", "collection_item_id"):
            completed_items.setdefault(course_progress_id, set()).add(
                collection_item_id
            )

        for record_id, form_item_ids in completed_form_item_ids_by_course_progress(
            batch
        ).items():
            completed_items.setdefault(record_id, set()).update(form_item_ids)

        for cp in all_course_progress.filter(pk__in=batch).iterator():
            new_percentage = calculate_course_progress_percentage(
                cp.course, completed_items.get(cp.pk, set())
            )

            if cp.progress_percentage != new_percentage:
                cp.progress_percentage = new_percentage
                cp.save(update_fields=["progress_percentage"])
                updated += 1

    click.echo(f"Recalculated {total} records, updated {updated}.")
