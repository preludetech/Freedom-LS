"""Create a cohort with learners at varying levels of course progress.

Creates an educator user, a cohort with 8-10 learners, registers the cohort
for a course, and creates progress records so learners are at different stages
of completion. Useful for demonstrating the Course Progress panel in the
educator interface.
"""

from typing import cast

import djclick as click
from guardian.shortcuts import assign_perm

from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import ContentCollectionItem, Course, Topic
from freedom_ls.form_engine.models import Form
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
)
from freedom_ls.learner_management.models import Cohort, CohortCourseRegistration
from freedom_ls.learner_progress.attempts import ensure_attempt
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.learner_progress.queries import course_progress_for
from freedom_ls.organisations.utils import get_default_organisation


def _collection_item_for(course: Course, child: Form | Topic) -> ContentCollectionItem:
    """The collection item placing `child` in `course`."""
    for collection_item in course.viewable_collection_items():
        if collection_item.child == child:
            return collection_item
    raise click.ClickException(
        f"'{child.slug}' is not a viewable item of '{course.slug}'."
    )


def _record_for(user: User, course: Course) -> CourseProgress:
    record = course_progress_for(user, course)
    if record is None:
        raise click.ClickException(
            f"No CourseProgress record for {user.email} on {course.slug}; "
            "register the learner before completing progress."
        )
    return record


def _complete_topic(user: User, course: Course, topic: Topic, site: Site) -> None:
    """Mark a topic as completed for a user."""
    record = _record_for(user, course)
    collection_item = _collection_item_for(course, topic)
    TopicProgress.objects.get_or_create(
        course_progress=record,
        collection_item=collection_item,
        defaults={"topic": topic, "site": site, "complete_time": timezone.now()},
    )


def _start_topic(user: User, course: Course, topic: Topic, site: Site) -> None:
    """Mark a topic as started (but not completed) for a user."""
    record = _record_for(user, course)
    collection_item = _collection_item_for(course, topic)
    TopicProgress.objects.get_or_create(
        course_progress=record,
        collection_item=collection_item,
        defaults={"topic": topic, "site": site},
    )


def _complete_form(user: User, course: Course, form: Form, site: Site) -> None:
    """Mark a form as completed for a user."""
    record = _record_for(user, course)
    collection_item = _collection_item_for(course, form)
    attempt = ensure_attempt(record, collection_item)
    if attempt.completed_time is None:
        attempt.completed_time = timezone.now()
        attempt.save(update_fields=["completed_time"])


def _start_form(user: User, course: Course, form: Form, site: Site) -> None:
    """Mark a form as started (but not completed) for a user."""
    record = _record_for(user, course)
    collection_item = _collection_item_for(course, form)
    ensure_attempt(record, collection_item)


def _set_course_progress(user: User, course: Course, percentage: int) -> None:
    """Set the course progress percentage for a user."""
    record = _record_for(user, course)
    record.progress_percentage = percentage
    record.save(update_fields=["progress_percentage"])


def _create_learner(site: Site, first_name: str, last_name: str, email: str) -> User:
    """Create a learner user, or return existing one."""
    try:
        return cast(User, User.objects.get(email=email))
    except User.DoesNotExist:
        return cast(
            User,
            UserFactory(
                email=email,
                first_name=first_name,
                last_name=last_name,
                password="testpass123",  # noqa: S106  # pragma: allowlist secret
                site=site,
            ),
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
    """Create a cohort with learners at varying progress levels through a course.

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

    # Gather course content items (CourseParts excluded — they aren't viewable destinations).
    children = course.viewable_items()
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
        cohort = CohortFactory(
            name=cohort_name, site=site, organisation=get_default_organisation(site)
        )
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
    educator = _create_learner(site, "Quinn", "Educator", educator_email)
    assign_perm("view_cohort", educator, cohort)
    click.secho(
        f"Educator: {educator_email} (password: testpass123) "
        f"- assigned 'view_cohort' permission on cohort",
        fg="green",
    )

    # Define learners with their progress profiles
    learner_profiles = [
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

    click.secho(f"\nCreating {len(learner_profiles)} learners:", fg="cyan")

    for (
        first,
        last,
        email_prefix,
        desc,
        n_topics_complete,
        n_topics_start,
        n_forms_complete,
        n_forms_start,
    ) in learner_profiles:
        email = f"qa-{email_prefix}@example.com"
        learner = _create_learner(site, first, last, email)

        # Add to cohort
        from freedom_ls.learner_management.models import CohortMembership

        if not CohortMembership.objects.filter(
            learner__user=learner, cohort=cohort, site=site
        ).exists():
            CohortMembershipFactory(
                learner__user=learner,
                learner__organisation=cohort.organisation,
                cohort=cohort,
                site=site,
            )

        # Create topic progress
        completed_count = 0
        for i, topic in enumerate(topics):
            if i < n_topics_complete:
                _complete_topic(learner, course, topic, site)
                completed_count += 1
            elif i < n_topics_complete + n_topics_start:
                _start_topic(learner, course, topic, site)

        # Create form progress
        for i, form in enumerate(forms):
            if i < n_forms_complete:
                _complete_form(learner, course, form, site)
                completed_count += 1
            elif i < n_forms_complete + n_forms_start:
                _start_form(learner, course, form, site)

        # Set course progress percentage
        if total_items > 0:
            percentage = round((completed_count / total_items) * 100)
        else:
            percentage = 0
        _set_course_progress(learner, course, percentage)

        click.secho(
            f"  {first} {last} <{email}> - {desc} "
            f"({completed_count}/{total_items} = {percentage}%)",
            fg="green",
        )

    click.secho("\n--- Summary ---", fg="cyan", bold=True)
    click.secho(f"Site: {site.name} ({site.domain})", fg="cyan")
    click.secho(f"Cohort: {cohort_name} (pk={cohort.pk})", fg="cyan")
    click.secho(f"Course: {course.title}", fg="cyan")
    click.secho(f"Learners: {len(learner_profiles)}", fg="cyan")
    click.secho(
        f"\nEducator login: {educator_email} / testpass123",
        fg="green",
        bold=True,
    )
    click.secho(
        "All learner passwords: testpass123",
        fg="green",
    )
    click.secho(
        f"\nView at: http://{site.domain}/educator/cohorts/{cohort.pk}",
        fg="cyan",
        bold=True,
    )
