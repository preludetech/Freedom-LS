"""Create a cohort with students at varying levels of course progress.

Creates an educator user, a cohort with 8-10 students, registers the cohort
for a course, and creates progress records so students are at different stages
of completion. Useful for demonstrating the Course Progress panel in the
educator interface.
"""

import djclick as click
from guardian.shortcuts import assign_perm

from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.models import Course, Form, Topic
from freedom_ls.student_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
)
from freedom_ls.student_management.models import Cohort, CohortCourseRegistration
from freedom_ls.student_progress.models import (
    CourseProgress,
    FormProgress,
    TopicProgress,
)


def _complete_topic(user: object, topic: Topic, site: Site) -> None:
    """Mark a topic as completed for a user."""
    TopicProgress.objects.get_or_create(
        user=user,
        topic=topic,
        site=site,
        defaults={"complete_time": timezone.now()},
    )


def _start_topic(user: object, topic: Topic, site: Site) -> None:
    """Mark a topic as started (but not completed) for a user."""
    TopicProgress.objects.get_or_create(
        user=user,
        topic=topic,
        site=site,
    )


def _complete_form(user: object, form: Form, site: Site) -> None:
    """Mark a form as completed for a user."""
    FormProgress.objects.get_or_create(
        user=user,
        form=form,
        site=site,
        defaults={"completed_time": timezone.now()},
    )


def _start_form(user: object, form: Form, site: Site) -> None:
    """Mark a form as started (but not completed) for a user."""
    FormProgress.objects.get_or_create(
        user=user,
        form=form,
        site=site,
    )


def _set_course_progress(
    user: object, course: Course, site: Site, percentage: int
) -> None:
    """Set the course progress percentage for a user."""
    # Use the base manager to bypass SiteAwareManager (no request context)
    CourseProgress.objects.update_or_create(
        user=user,
        course=course,
        site=site,
        defaults={"progress_percentage": percentage},
    )


def _create_student(site: Site, first_name: str, last_name: str, email: str) -> object:
    """Create a student user, or return existing one."""
    from freedom_ls.accounts.models import User

    try:
        return User.objects.get(email=email)
    except User.DoesNotExist:
        return UserFactory(
            email=email,
            first_name=first_name,
            last_name=last_name,
            password="testpass123",  # noqa: S106  # pragma: allowlist secret
            site=site,
        )


@click.command()
@click.argument("site_name")
@click.option(
    "--course-slug",
    default="functionality-demo-course-parts",
    help="Slug of the course to use (default: functionality-demo-course-parts)",
)
@click.option(
    "--cohort-name",
    default="QA Progress Demo Cohort",
    help="Name for the cohort (default: 'QA Progress Demo Cohort')",
)
def command(
    site_name: str,
    course_slug: str,
    cohort_name: str,
) -> None:
    """Create a cohort with students at varying progress levels through a course.

    SITE_NAME is the name of the site to create data on (e.g. 'DemoDev').
    """
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e

    try:
        course = Course.objects.get(slug=course_slug, site=site)
    except Course.DoesNotExist as e:
        available = list(
            Course.objects.filter(site=site).values_list("slug", flat=True)
        )
        raise click.ClickException(
            f"Course '{course_slug}' not found on site '{site_name}'. "
            f"Available: {available}"
        ) from e

    # Gather course content items
    children = course.children_flat()
    topics = [c for c in children if isinstance(c, Topic)]
    forms = [c for c in children if isinstance(c, Form)]
    total_items = len(topics) + len(forms)

    click.secho(
        f"Course: {course.title} ({len(topics)} topics, {len(forms)} forms)",
        fg="cyan",
    )

    # Create or get cohort
    try:
        cohort = Cohort.objects.get(name=cohort_name, site=site)
        click.secho(f"Cohort '{cohort_name}' already exists, reusing it", fg="yellow")
    except Cohort.DoesNotExist:
        cohort = CohortFactory(name=cohort_name, site=site)
        click.secho(f"Created cohort '{cohort_name}'", fg="green")

    # Register cohort for course
    if not CohortCourseRegistration.objects.filter(
        cohort=cohort, collection=course, site=site
    ).exists():
        CohortCourseRegistrationFactory(cohort=cohort, collection=course, site=site)
        click.secho(f"Registered cohort for course '{course.title}'", fg="green")
    else:
        click.secho(f"Already registered for '{course.title}'", fg="yellow")

    # Create educator user
    educator_email = "qa-educator-progress@example.com"
    educator = _create_student(site, "Quinn", "Educator", educator_email)
    assign_perm("view_cohort", educator, cohort)
    click.secho(
        f"Educator: {educator_email} (password: testpass123) "
        f"- assigned 'view_cohort' permission on cohort",
        fg="green",
    )

    # Define students with their progress profiles
    student_profiles = [
        # (first, last, email_prefix, description, topics_to_complete, topics_to_start, forms_to_complete, forms_to_start)
        ("Alice", "Zero", "alice.zero", "no progress", 0, 0, 0, 0),
        ("Bob", "Nada", "bob.nada", "no progress", 0, 0, 0, 0),
        ("Carol", "Starter", "carol.starter", "started a few topics", 0, 2, 0, 0),
        (
            "Dave",
            "Beginner",
            "dave.beginner",
            "started some, completed one",
            1,
            2,
            0,
            0,
        ),
        ("Eve", "Middle", "eve.middle", "moderate progress", 2, 1, 1, 0),
        ("Frank", "Halfway", "frank.halfway", "moderate progress", 3, 1, 0, 1),
        ("Grace", "Advanced", "grace.advanced", "nearly done", 4, 1, 1, 1),
        ("Hank", "Almost", "hank.almost", "nearly complete", 5, 0, 1, 1),
        ("Ivy", "Done", "ivy.done", "fully complete", 5, 0, 2, 0),
    ]

    click.secho(f"\nCreating {len(student_profiles)} students:", fg="cyan")

    for (
        first,
        last,
        email_prefix,
        desc,
        n_topics_complete,
        n_topics_start,
        n_forms_complete,
        n_forms_start,
    ) in student_profiles:
        email = f"qa-{email_prefix}@example.com"
        student = _create_student(site, first, last, email)

        # Add to cohort
        from freedom_ls.student_management.models import CohortMembership

        if not CohortMembership.objects.filter(
            user=student, cohort=cohort, site=site
        ).exists():
            CohortMembershipFactory(user=student, cohort=cohort, site=site)

        # Create topic progress
        completed_count = 0
        for i, topic in enumerate(topics):
            if i < n_topics_complete:
                _complete_topic(student, topic, site)
                completed_count += 1
            elif i < n_topics_complete + n_topics_start:
                _start_topic(student, topic, site)

        # Create form progress
        for i, form in enumerate(forms):
            if i < n_forms_complete:
                _complete_form(student, form, site)
                completed_count += 1
            elif i < n_forms_complete + n_forms_start:
                _start_form(student, form, site)

        # Set course progress percentage
        if total_items > 0:
            percentage = round((completed_count / total_items) * 100)
        else:
            percentage = 0
        _set_course_progress(student, course, site, percentage)

        click.secho(
            f"  {first} {last} <{email}> - {desc} "
            f"({completed_count}/{total_items} = {percentage}%)",
            fg="green",
        )

    click.secho("\n--- Summary ---", fg="cyan", bold=True)
    click.secho(f"Site: {site.name} ({site.domain})", fg="cyan")
    click.secho(f"Cohort: {cohort_name} (pk={cohort.pk})", fg="cyan")
    click.secho(f"Course: {course.title}", fg="cyan")
    click.secho(f"Students: {len(student_profiles)}", fg="cyan")
    click.secho(
        f"\nEducator login: {educator_email} / testpass123",
        fg="green",
        bold=True,
    )
    click.secho(
        "All student passwords: testpass123",
        fg="green",
    )
    click.secho(
        f"\nView at: http://{site.domain}/educator/cohorts/{cohort.pk}",
        fg="cyan",
        bold=True,
    )
