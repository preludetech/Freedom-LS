import djclick as click
from django.db import transaction

from freedom_ls.content_engine.models import (
    Topic,
    Activity,
    Course,
    ContentCollectionItem,
    Form,
    FormPage,
    FormContent,
    FormQuestion,
    QuestionOption,
    File,
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
            "\nWARNING: This will permanently delete ALL content!",
            fg="red",
            bold=True
        )
        if not click.confirm("Are you sure you want to continue?"):
            click.secho("Deletion cancelled.", fg="green")
            return

    # Delete all content in a transaction
    click.secho("\nDeleting content...", fg="yellow")

    with transaction.atomic():
        deleted_counts = {}

        # Delete in reverse dependency order to avoid FK issues
        # (though CASCADE should handle it)
        for name, model in models_to_delete:
            count, _ = model.objects.all().delete()
            if count > 0:
                deleted_counts[name] = count

    # Report results
    click.secho("\nDeletion complete!", fg="green", bold=True)
    for name, count in deleted_counts.items():
        click.secho(f"  Deleted {count} {name}", fg="green")
