"""Create a cohort with course registrations but no students."""

import djclick as click
from django.contrib.sites.models import Site

from freedom_ls.content_engine.models import Course
from freedom_ls.student_management.models import Cohort, CohortCourseRegistration


@click.command()
@click.argument("site_name")
@click.option(
    "--cohort-name",
    default="QA Empty Students Cohort",
    help="Name for the cohort (default: 'QA Empty Students Cohort')",
)
@click.option(
    "--course-slug",
    required=True,
    multiple=True,
    help="Course slug(s) to register. Can be specified multiple times.",
)
def command(
    site_name: str,
    cohort_name: str,
    course_slug: tuple[str, ...],
) -> None:
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist:
        raise click.ClickException(f"Site with name '{site_name}' not found.")

    cohort, created = Cohort.objects.get_or_create(name=cohort_name, site=site)
    if created:
        click.secho(f"Created cohort '{cohort_name}' (no students)", fg="green")
    else:
        click.secho(f"Cohort '{cohort_name}' already exists", fg="yellow")

    for slug in course_slug:
        try:
            course = Course.objects.get(slug=slug, site=site)
        except Course.DoesNotExist:
            click.secho(f"Course with slug '{slug}' not found", fg="red")
            continue

        _, reg_created = CohortCourseRegistration.objects.get_or_create(
            collection=course, cohort=cohort, site=site
        )
        if reg_created:
            click.secho(f"Registered cohort for course '{course.title}'", fg="green")
        else:
            click.secho(f"Already registered for '{course.title}'", fg="yellow")

    click.secho(
        f"\nCohort '{cohort_name}' has course registrations but zero students.",
        fg="green",
    )
