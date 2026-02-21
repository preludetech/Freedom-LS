"""Create a cohort with many students for testing row pagination."""

import djclick as click
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site

from freedom_ls.student_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Student,
)

User = get_user_model()


@click.command()
@click.argument("site_name")
@click.option(
    "--cohort-name",
    default="QA Large Cohort",
    help="Name for the cohort (default: 'QA Large Cohort')",
)
@click.option(
    "--num-students",
    default=25,
    type=int,
    help="Number of students to create (default: 25)",
)
@click.option(
    "--course-slug",
    multiple=True,
    help="Course slug(s) to register the cohort for. Can be specified multiple times.",
)
def command(
    site_name: str,
    cohort_name: str,
    num_students: int,
    course_slug: tuple[str, ...],
) -> None:
    from freedom_ls.content_engine.models import Course

    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist:
        raise click.ClickException(f"Site with name '{site_name}' not found.")

    cohort, created = Cohort.objects.get_or_create(name=cohort_name, site=site)
    if created:
        click.secho(f"Created cohort '{cohort_name}'", fg="green")
    else:
        click.secho(f"Cohort '{cohort_name}' already exists", fg="yellow")

    # Create students and add to cohort
    created_count = 0
    for i in range(1, num_students + 1):
        email = f"qa_student_{i}@example.com"
        user, user_created = User.objects.get_or_create(
            email=email,
            site=site,
            defaults={
                "first_name": "QA Student",
                "last_name": str(i),
                "is_active": True,
            },
        )
        if user_created:
            user.set_password("testpass123")
            user.save()

        student, _ = Student.objects.get_or_create(user=user, site=site)
        _, membership_created = CohortMembership.objects.get_or_create(
            student=student, cohort=cohort, site=site
        )
        if membership_created:
            created_count += 1

    click.secho(
        f"Added {created_count} new students to '{cohort_name}' "
        f"(total requested: {num_students})",
        fg="green",
    )

    # Register courses if specified
    for slug in course_slug:
        try:
            course = Course.objects.get(slug=slug, site=site)
        except Course.DoesNotExist:
            click.secho(
                f"Course with slug '{slug}' not found on site '{site_name}'",
                fg="red",
            )
            continue

        _, reg_created = CohortCourseRegistration.objects.get_or_create(
            collection=course, cohort=cohort, site=site
        )
        if reg_created:
            click.secho(f"Registered cohort for course '{course.title}'", fg="green")
        else:
            click.secho(
                f"Cohort already registered for '{course.title}'", fg="yellow"
            )
