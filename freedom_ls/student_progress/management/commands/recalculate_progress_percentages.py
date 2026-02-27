from uuid import UUID

import djclick as click
from freedom_ls.student_progress.models import CourseProgress, TopicProgress, FormProgress
from freedom_ls.student_management.utils import calculate_course_progress_percentage


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

    # Batch-fetch all completed items, grouped by user_id
    completed_topics_by_user: dict[int, set[UUID]] = {}
    for user_id, topic_id in TopicProgress.objects.filter(
        complete_time__isnull=False
    ).values_list("user_id", "topic_id"):
        completed_topics_by_user.setdefault(user_id, set()).add(topic_id)

    completed_forms_by_user: dict[int, set[UUID]] = {}
    for user_id, form_id in FormProgress.objects.filter(
        completed_time__isnull=False
    ).values_list("user_id", "form_id"):
        completed_forms_by_user.setdefault(user_id, set()).add(form_id)

    updated = 0
    for cp in all_course_progress.iterator():
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
