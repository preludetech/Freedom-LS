import djclick as click

from django.db import transaction

from freedom_ls.dev_tools.guard import require_dev_tools_enabled
from freedom_ls.form_engine import models as form_models
from freedom_ls.learner_progress import models

# Same order as danger_content_delete: QuestionAnswer.question and the two
# course-progress rows below it are PROTECTed by content further down the
# chain, so they clear first.
models_to_delete = [
    ("Question Answers", form_models.QuestionAnswer),
    ("Course Form Attempts", models.CourseFormAttempt),
    ("Form Progress", form_models.FormProgress),
    ("Topic Progress", models.TopicProgress),
    ("Course Progress", models.CourseProgress),
]


@click.command()
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt and delete all progress immediately",
)
def command(yes: bool) -> None:
    """
    Delete all learner progress against every course.

    WARNING: This is a destructive operation that cannot be undone!
    """
    require_dev_tools_enabled()

    click.secho("\nProgress to be deleted:", fg="yellow", bold=True)
    total_count = 0
    for name, model in models_to_delete:
        count = model.objects.all().count()
        total_count += count
        if count > 0:
            click.secho(f"  {name}: {count}", fg="yellow")

    if total_count == 0:
        click.secho("\nNo progress found to delete.", fg="green")
        return

    click.secho(f"\nTotal items to delete: {total_count}", fg="red", bold=True)

    if not yes:
        click.secho(
            "\nWARNING: This will permanently delete ALL course progress!",
            fg="red",
            bold=True,
        )
        if not click.confirm("Are you sure you want to continue?"):
            click.secho("Deletion cancelled.", fg="green")
            return

    click.secho("\nDeleting progress...", fg="yellow")

    with transaction.atomic():
        deleted_counts = {}
        for name, model in models_to_delete:
            count, _ = model.objects.all().delete()
            if count > 0:
                deleted_counts[name] = count

    click.secho("\nDeletion complete!", fg="green", bold=True)
    for name, count in deleted_counts.items():
        click.secho(f"  Deleted {count} {name}", fg="green")
