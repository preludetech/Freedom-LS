from itertools import batched
from uuid import UUID

import djclick as click

from freedom_ls.student_management.utils import calculate_course_progress_percentage
from freedom_ls.student_progress.models import (
    CourseProgress,
    TopicProgress,
)
from freedom_ls.student_progress.queries import completed_form_ids_by_user

# Learners per batch. The command walks every CourseProgress row in the
# installation, and the completed-item lookups it needs are model instances, not
# id tuples — fetching them for all learners at once is what makes this a
# memory-bound command instead of a scan.
USER_BATCH_SIZE = 500


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

    user_ids = list(
        CourseProgress.objects.values_list("user_id", flat=True).distinct().iterator()
    )

    updated = 0
    for batch in batched(user_ids, USER_BATCH_SIZE, strict=False):
        # Batch-fetch this batch's completed items, grouped by user_id
        completed_topics_by_user: dict[int, set[UUID]] = {}
        for user_id, topic_id in TopicProgress.objects.filter(
            user_id__in=batch, complete_time__isnull=False
        ).values_list("user_id", "topic_id"):
            completed_topics_by_user.setdefault(user_id, set()).add(topic_id)

        completed_forms_by_user = completed_form_ids_by_user(batch)

        for cp in all_course_progress.filter(user_id__in=batch).iterator():
            completed_topic_ids = completed_topics_by_user.get(cp.user_id, set())
            completed_form_ids = completed_forms_by_user.get(cp.user_id, set())

            new_percentage = calculate_course_progress_percentage(
                cp.course, completed_topic_ids, completed_form_ids
            )

            if cp.progress_percentage != new_percentage:
                cp.progress_percentage = new_percentage
                cp.save(update_fields=["progress_percentage"])
                updated += 1

    click.echo(f"Recalculated {total} records, updated {updated}.")
