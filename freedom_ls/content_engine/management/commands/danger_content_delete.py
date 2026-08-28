import djclick as click

from django.apps import apps
from django.db import transaction

from freedom_ls.content_engine.models import (
    Activity,
    ContentCollectionItem,
    Course,
    File,
    Topic,
)
from freedom_ls.form_engine.models import (
    Form,
    FormContent,
    FormPage,
    FormQuestion,
    QuestionOption,
)


@click.command()
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt and delete all content immediately",
)
def command(yes: bool) -> None:
    """
    Delete all content from the content engine.

    WARNING: This is a destructive operation that cannot be undone!
    """
    # Get counts before deletion
    models_to_delete = [
        ("Topics", Topic),
        ("Activities", Activity),
        ("Courses", Course),
        ("Collection Items", ContentCollectionItem),
        ("Forms", Form),
        ("Form Pages", FormPage),
        ("Form Content", FormContent),
        ("Form Questions", FormQuestion),
        ("Question Options", QuestionOption),
        ("Files", File),
    ]

    click.secho("\nContent to be deleted:", fg="yellow", bold=True)
    total_count = 0
    for name, model in models_to_delete:
        count = model.objects.all().count()
        total_count += count
        if count > 0:
            click.secho(f"  {name}: {count}", fg="yellow")

    if total_count == 0:
        click.secho("\nNo content found to delete.", fg="green")
        return

    click.secho(f"\nTotal items to delete: {total_count}", fg="red", bold=True)

    # Confirm deletion
    if not yes:
        click.secho(
            "\nWARNING: This will permanently delete ALL content!", fg="red", bold=True
        )
        if not click.confirm("Are you sure you want to continue?"):
            click.secho("Deletion cancelled.", fg="green")
            return

    # Delete all content in a transaction
    click.secho("\nDeleting content...", fg="yellow")

    with transaction.atomic():
        deleted_counts = {}

        # Progress is PROTECTed against content deletion, so it is cleared
        # first and deliberately: deleting all content while keeping progress
        # pointing at it is not a state anyone wants. QuestionAnswer.question is
        # PROTECTed the same way, so it goes first here too -- move it later and
        # the FormQuestion delete below fails. Course registrations PROTECT the
        # course they name, so they come after CourseProgress (which PROTECTs
        # the registration that granted it) and before the course delete below.
        # Same order as danger_clear_all_course_progress. Fetched through the
        # app registry rather than imported, so content_engine gains no
        # dependency on either app -- both already depend on it.
        for app_label, label in (
            ("freedom_ls_form_engine", "QuestionAnswer"),
            ("freedom_ls_learner_progress", "CourseFormAttempt"),
            ("freedom_ls_form_engine", "FormProgress"),
            ("freedom_ls_learner_progress", "TopicProgress"),
            ("freedom_ls_learner_progress", "CourseProgress"),
            ("freedom_ls_learner_management", "LearnerCourseRegistration"),
            ("freedom_ls_learner_management", "CohortCourseRegistration"),
        ):
            apps.get_model(app_label, label).objects.all().delete()

        # Delete in reverse dependency order to avoid FK issues
        for name, model in models_to_delete:
            count, _ = model.objects.all().delete()
            if count > 0:
                deleted_counts[name] = count

    # Report results
    click.secho("\nDeletion complete!", fg="green", bold=True)
    for name, count in deleted_counts.items():
        click.secho(f"  Deleted {count} {name}", fg="green")
