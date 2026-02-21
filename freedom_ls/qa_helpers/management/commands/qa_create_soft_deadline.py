"""Create a soft cohort deadline for QA testing overdue styling."""

import djclick as click
from django.contrib.contenttypes.models import ContentType as DjangoContentType
from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.content_engine.models import Form, Topic
from freedom_ls.student_management.models import (
    CohortCourseRegistration,
    CohortDeadline,
)


@click.command()
@click.argument("site_name")
@click.option("--cohort-name", required=True, help="Name of the cohort")
@click.option("--course-slug", required=True, help="Slug of the course")
@click.option(
    "--item-slug",
    default=None,
    help="Slug of a specific topic or form. If omitted, creates a course-level deadline.",
)
@click.option(
    "--days-from-now",
    default=-7,
    type=int,
    help="Deadline N days from now. Negative = past (overdue). (default: -7)",
)
@click.option(
    "--hard",
    is_flag=True,
    default=False,
    help="Make this a hard deadline (default is soft)",
)
def command(
    site_name: str,
    cohort_name: str,
    course_slug: str,
    item_slug: str | None,
    days_from_now: int,
    hard: bool,
) -> None:
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist:
        raise click.ClickException(f"Site with name '{site_name}' not found.")

    try:
        registration = CohortCourseRegistration.objects.select_related(
            "cohort", "collection"
        ).get(
            cohort__name=cohort_name,
            collection__slug=course_slug,
            site=site,
        )
    except CohortCourseRegistration.DoesNotExist:
        raise click.ClickException(
            f"No course registration found for cohort '{cohort_name}' and course '{course_slug}'."
        )

    deadline = timezone.now() + timezone.timedelta(days=days_from_now)

    content_type = None
    object_id = None

    if item_slug:
        topic = Topic.objects.filter(slug=item_slug, site=site).first()
        form = Form.objects.filter(slug=item_slug, site=site).first()

        if topic:
            content_type = DjangoContentType.objects.get_for_model(Topic)
            object_id = topic.id
            item_name = topic.title
        elif form:
            content_type = DjangoContentType.objects.get_for_model(Form)
            object_id = form.id
            item_name = form.title
        else:
            raise click.ClickException(f"No topic or form found with slug '{item_slug}'.")
    else:
        item_name = "course-level"

    deadline_obj, created = CohortDeadline.objects.update_or_create(
        cohort_course_registration=registration,
        content_type=content_type,
        object_id=object_id,
        site=site,
        defaults={
            "deadline": deadline,
            "is_hard_deadline": hard,
        },
    )

    deadline_type = "hard" if hard else "soft"
    if created:
        click.secho(
            f"Created {deadline_type} deadline on {item_name}: "
            f"{deadline.strftime('%Y-%m-%d %H:%M')}",
            fg="green",
        )
    else:
        click.secho(
            f"Updated existing deadline on {item_name} to {deadline_type}: "
            f"{deadline.strftime('%Y-%m-%d %H:%M')}",
            fg="green",
        )
