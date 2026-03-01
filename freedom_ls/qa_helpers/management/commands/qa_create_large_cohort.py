"""Create a cohort with many students for testing row pagination."""

import djclick as click

from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.student_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    StudentFactory,
)
from freedom_ls.student_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Student,
)


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
    except Site.DoesNotExist as e:
        raise click.ClickException(f"Site with name '{site_name}' not found.") from e

    try:
        cohort = Cohort.objects.get(name=cohort_name, site=site)
        click.secho(f"Cohort '{cohort_name}' already exists", fg="yellow")
    except Cohort.DoesNotExist:
        cohort = CohortFactory(name=cohort_name, site=site)
        click.secho(f"Created cohort '{cohort_name}'", fg="green")

    # Create students and add to cohort
    created_count = 0
    for i in range(1, num_students + 1):
        email = f"qa_student_{i}@example.com"
        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        user = None
        try:
            user = user_model.objects.get(email=email, site=site)
        except user_model.DoesNotExist:
            user = UserFactory(
                email=email,
                first_name="QA Student",
                last_name=str(i),
                is_active=True,
                password="testpass123",  # noqa: S106
                site=site,
            )

        try:
            student = Student.objects.get(user=user, site=site)
        except Student.DoesNotExist:
            student = StudentFactory(user=user, site=site)

        if not CohortMembership.objects.filter(
            student=student, cohort=cohort, site=site
        ).exists():
            CohortMembershipFactory(student=student, cohort=cohort, site=site)
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

        if not CohortCourseRegistration.objects.filter(
            collection=course, cohort=cohort, site=site
        ).exists():
            CohortCourseRegistrationFactory(collection=course, cohort=cohort, site=site)
            click.secho(f"Registered cohort for course '{course.title}'", fg="green")
        else:
            click.secho(f"Cohort already registered for '{course.title}'", fg="yellow")
