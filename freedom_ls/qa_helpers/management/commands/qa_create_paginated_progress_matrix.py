"""Seed an organisation-owned cohort whose course-progress matrix paginates both ways.

The educator course-progress panel (``CohortCourseProgressPanel``) runs two
independent paginators: columns over the course's flat collection items
(Topic + Form placements, CourseParts excluded) at ``COLUMN_PAGE_SIZE`` (15),
and rows over ``CohortMembership`` at ``LEARNER_PAGE_SIZE`` (20). Exercising
both at once needs a course with more items than one column page and a cohort
with more members than one learner page.

``qa_create_column_pagination_scenario`` builds the minimal version of that pair
in the site's default organisation and leaves every learner at 0%. This command
builds the larger, organisation-scoped version the progress-matrix QA needs: a
cohort inside a real organisation (so an organisation-staff educator reaches it
through ``/educator/organisations/<slug>/``), 30+ members, 25+ items, and a
spread of completions from empty through part-way to finished.

Percentages are recalculated from the completion rows this command writes,
because ``TopicProgress`` rows created already-complete never make the
not-complete -> complete transition the recalculation receiver watches for.
Only this cohort's records are touched, so deliberately-stale percentages
elsewhere in the dev database survive.

Idempotent.
"""

from typing import cast

import djclick as click
from guardian.shortcuts import assign_perm

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.db.models import Max
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    CoursePartFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CoursePart,
    CourseVisibility,
    Topic,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
)
from freedom_ls.learner_management.utils import calculate_course_progress_percentage
from freedom_ls.learner_progress.factories import TopicProgressFactory
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress
from freedom_ls.organisations.models import Organisation

COURSE_SLUG = "qa-pagination-matrix-course"
COURSE_TITLE = "QA Pagination Matrix Course"
PART_SLUG_TEMPLATE = "qa-pagination-matrix-part-{index}"
PART_TITLE_TEMPLATE = "QA Pagination Matrix Part {index}"
TOPIC_SLUG_TEMPLATE = "qa-pagination-matrix-topic-{index:02d}"
TOPIC_TITLE_TEMPLATE = "QA Pagination Matrix Topic {index:02d}"
LEARNER_EMAIL_TEMPLATE = "qa_pagmatrix_learner_{index:02d}@example.com"
LEARNER_PASSWORD = "testpass123"  # noqa: S105  # pragma: allowlist secret

#: How many members sit at each end of the spread. The rest are spaced evenly
#: between one completed item and one short of the whole course.
EMPTY_LEARNERS = 6
FINISHED_LEARNERS = 6

#: The course is split over two parts so the panel also renders part headers
#: spanning their visible columns on both column pages.
PART_COUNT = 2


def _next_order(collection: Course | CoursePart, site: Site) -> int:
    """The order value placing a new child last in this collection."""
    collection_ctype = ContentType.objects.get_for_model(type(collection))
    highest = ContentCollectionItem.objects.filter(
        collection_type=collection_ctype, collection_id=collection.pk, site=site
    ).aggregate(Max("order"))["order__max"]
    return 0 if highest is None else highest + 1


def _is_placed_in(
    collection: Course | CoursePart, child: CoursePart | Topic, site: Site
) -> bool:
    """Whether `child` already has a placement inside `collection`."""
    return ContentCollectionItem.objects.filter(
        collection_type=ContentType.objects.get_for_model(type(collection)),
        collection_id=collection.pk,
        child_type=ContentType.objects.get_for_model(type(child)),
        child_id=child.pk,
        site=site,
    ).exists()


def _ensure_course(site: Site) -> Course:
    """The QA course, created published and free if it is missing."""
    course: Course | None = Course.objects.filter(slug=COURSE_SLUG, site=site).first()
    if course is not None:
        click.secho(f"Reusing course '{course.title}' ({COURSE_SLUG})", fg="yellow")
        return course

    course = cast(
        Course,
        CourseFactory(
            title=COURSE_TITLE,
            slug=COURSE_SLUG,
            site=site,
            visibility=CourseVisibility.PUBLISHED,
            access_config={"access_type": "free"},
        ),
    )
    click.secho(f"Created course '{course.title}' ({COURSE_SLUG})", fg="green")
    return course


def _ensure_parts(site: Site, course: Course) -> list[CoursePart]:
    """The course's QA parts, in order, created and attached if missing."""
    parts: list[CoursePart] = []
    for index in range(1, PART_COUNT + 1):
        slug = PART_SLUG_TEMPLATE.format(index=index)
        part: CoursePart | None = CoursePart.objects.filter(
            slug=slug, site=site
        ).first()
        if part is None:
            part = cast(
                CoursePart,
                CoursePartFactory(
                    title=PART_TITLE_TEMPLATE.format(index=index), slug=slug, site=site
                ),
            )
            click.secho(f"  + Created part '{part.title}'", fg="green")
        if not _is_placed_in(course, part, site):
            ContentCollectionItemFactory(
                collection_object=course,
                child_object=part,
                order=_next_order(course, site),
                site=site,
            )
            click.secho(f"  + Attached part '{part.title}' to the course", fg="green")
        parts.append(part)
    return parts


def _ensure_topics(site: Site, parts: list[CoursePart], target_item_count: int) -> int:
    """Place `target_item_count` topics across the parts. Returns how many were added."""
    per_part = -(-target_item_count // len(parts))  # ceiling division
    added = 0
    for index in range(1, target_item_count + 1):
        part = parts[min((index - 1) // per_part, len(parts) - 1)]
        slug = TOPIC_SLUG_TEMPLATE.format(index=index)
        topic: Topic | None = Topic.objects.filter(slug=slug, site=site).first()
        if topic is None:
            topic = cast(
                Topic,
                TopicFactory(
                    title=TOPIC_TITLE_TEMPLATE.format(index=index),
                    slug=slug,
                    site=site,
                ),
            )
        if not _is_placed_in(part, topic, site):
            ContentCollectionItemFactory(
                collection_object=part,
                child_object=topic,
                order=_next_order(part, site),
                site=site,
            )
            added += 1
    return added


def _ensure_cohort(site: Site, organisation: Organisation, cohort_name: str) -> Cohort:
    """The QA cohort inside `organisation`, created if it is missing."""
    cohort: Cohort | None = Cohort.objects.filter(
        name=cohort_name, site=site, organisation=organisation
    ).first()
    if cohort is not None:
        click.secho(f"Reusing cohort '{cohort_name}'", fg="yellow")
        return cohort

    cohort = cast(
        Cohort,
        CohortFactory(name=cohort_name, site=site, organisation=organisation),
    )
    click.secho(f"Created cohort '{cohort_name}' in '{organisation.name}'", fg="green")
    return cohort


def _ensure_registration(
    site: Site, cohort: Cohort, course: Course
) -> CohortCourseRegistration:
    """The cohort's active registration for the QA course.

    Creating it fans out a CourseProgress record to every current member; the
    membership receiver catches up anyone added afterwards.
    """
    registration: CohortCourseRegistration | None = (
        CohortCourseRegistration.objects.filter(
            cohort=cohort, course=course, site=site
        ).first()
    )
    if registration is not None:
        if not registration.is_active:
            registration.is_active = True
            registration.save(update_fields=["is_active"])
            click.secho("Reactivated the cohort's course registration", fg="green")
        else:
            click.secho(f"Cohort already registered for '{course.title}'", fg="yellow")
        return registration

    registration = cast(
        CohortCourseRegistration,
        CohortCourseRegistrationFactory(
            cohort=cohort, course=course, site=site, is_active=True
        ),
    )
    click.secho(f"Registered cohort for '{course.title}'", fg="green")
    return registration


def _ensure_members(site: Site, cohort: Cohort, num_learners: int) -> list[User]:
    """The cohort's QA learners, in index order, created and enrolled if missing."""
    learners: list[User] = []
    added = 0
    for index in range(1, num_learners + 1):
        email = LEARNER_EMAIL_TEMPLATE.format(index=index)
        user: User | None = User.objects.filter(email=email).first()
        if user is None:
            user = cast(
                User,
                UserFactory(
                    email=email,
                    first_name="Pagmatrix",
                    last_name=f"Learner {index:02d}",
                    is_active=True,
                    password=LEARNER_PASSWORD,
                    site=site,
                ),
            )
        if not CohortMembership.objects.filter(
            learner__user=user, cohort=cohort, site=site
        ).exists():
            CohortMembershipFactory(
                learner__user=user,
                learner__organisation=cohort.organisation,
                cohort=cohort,
                site=site,
            )
            added += 1
        learners.append(user)
    click.secho(f"Cohort members added this run: {added}", fg="green")
    return learners


def _completed_item_count(index: int, num_learners: int, total_items: int) -> int:
    """How many items the learner at 1-based `index` should have finished.

    The first `EMPTY_LEARNERS` have never started, the last `FINISHED_LEARNERS`
    are done, and everyone between is spaced evenly over the range in between.
    """
    if index <= EMPTY_LEARNERS:
        return 0
    if index > num_learners - FINISHED_LEARNERS:
        return total_items

    partway_count = num_learners - EMPTY_LEARNERS - FINISHED_LEARNERS
    position = index - EMPTY_LEARNERS
    completed = round(position * (total_items - 1) / (partway_count + 1))
    return max(1, min(total_items - 1, completed))


def _apply_progress(
    site: Site,
    registration: CohortCourseRegistration,
    course: Course,
    learners: list[User],
) -> dict[str, int]:
    """Write the completion spread and refresh every affected percentage.

    Returns a count of learners per band, for the summary.
    """
    collection_items = course.viewable_collection_items()
    total_items = len(collection_items)
    bands = {"none": 0, "partway": 0, "complete": 0}

    for index, user in enumerate(learners, start=1):
        record: CourseProgress | None = CourseProgress.objects.filter(
            cohort_registration=registration, learner__user=user
        ).first()
        if record is None:
            raise click.ClickException(
                f"No CourseProgress record for {user.email} on this registration; "
                "the registration receivers did not fan out."
            )

        completed = _completed_item_count(index, len(learners), total_items)
        for position, collection_item in enumerate(collection_items):
            is_complete = position < completed
            # One started-but-unfinished item after the completed run, so the
            # matrix shows in-progress cells as well as done and untouched ones.
            is_started = position == completed and 0 < completed < total_items
            if not (is_complete or is_started):
                continue
            if TopicProgress.objects.filter(
                course_progress=record, collection_item=collection_item
            ).exists():
                continue
            TopicProgressFactory(
                course_progress=record,
                collection_item=collection_item,
                topic=collection_item.child,
                complete_time=timezone.now() if is_complete else None,
                site=site,
            )

        _refresh_percentage(record, course)

        if completed == 0:
            bands["none"] += 1
        elif completed == total_items:
            bands["complete"] += 1
        else:
            bands["partway"] += 1

    return bands


def _refresh_percentage(record: CourseProgress, course: Course) -> None:
    """Recompute this record's stored percentage from its completion rows.

    A TopicProgress row created already-complete never makes the transition
    `recalculate_course_progress_on_save` watches for, so the percentage has to
    be written here or it would stay at the registration's initial 0.
    """
    completed_item_ids = set(
        TopicProgress.objects.filter(
            course_progress=record,
            complete_time__isnull=False,
            collection_item__isnull=False,
        ).values_list("collection_item_id", flat=True)
    )
    percentage = calculate_course_progress_percentage(course, completed_item_ids)
    fields = ["progress_percentage"]
    record.progress_percentage = percentage
    if percentage == 100 and record.completed_time is None:
        record.completed_time = timezone.now()
        fields.append("completed_time")
    record.save(update_fields=fields)


@click.command()
@click.argument("site_name", default="DemoDev")
@click.option(
    "--organisation-slug",
    default="rpas-training",
    help="Organisation to own the cohort (default: rpas-training).",
)
@click.option(
    "--cohort-name",
    default="QA Pagination Cohort",
    help="Cohort name (default: 'QA Pagination Cohort').",
)
@click.option(
    "--num-learners",
    default=32,
    type=int,
    help="Cohort size; must exceed 20 for the learner paginator (default: 32).",
)
@click.option(
    "--target-item-count",
    default=26,
    type=int,
    help="Flat course items; must exceed 15 for the column paginator (default: 26).",
)
@click.option(
    "--educator-email",
    multiple=True,
    default=("org.educator@example.com",),
    help="Educator(s) to grant object-level view_cohort on the cohort.",
)
def command(
    site_name: str,
    organisation_slug: str,
    cohort_name: str,
    num_learners: int,
    target_item_count: int,
    educator_email: tuple[str, ...],
) -> None:
    """Seed an organisation-owned cohort whose progress matrix paginates both ways.

    SITE_NAME is the name of the site to seed (e.g. 'DemoDev').
    """
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e

    try:
        organisation = Organisation.objects.get(slug=organisation_slug, site=site)
    except Organisation.DoesNotExist as e:
        available = list(
            Organisation.objects.filter(site=site).values_list("slug", flat=True)
        )
        raise click.ClickException(
            f"Organisation '{organisation_slug}' not found on site '{site_name}'. "
            f"Available: {available}"
        ) from e

    if num_learners <= EMPTY_LEARNERS + FINISHED_LEARNERS:
        raise click.ClickException(
            f"--num-learners must exceed {EMPTY_LEARNERS + FINISHED_LEARNERS} so the "
            "spread has learners between the empty and finished bands."
        )

    click.secho("Building course:", fg="cyan")
    course = _ensure_course(site)
    parts = _ensure_parts(site, course)
    added_topics = _ensure_topics(site, parts, target_item_count)
    click.secho(f"  Topics placed this run: {added_topics}", fg="green")

    # Re-query: collection_items() and children() are memoized per instance.
    course = Course.objects.get(pk=course.pk)

    click.secho("\nBuilding cohort:", fg="cyan")
    cohort = _ensure_cohort(site, organisation, cohort_name)
    registration = _ensure_registration(site, cohort, course)
    learners = _ensure_members(site, cohort, num_learners)

    click.secho("\nApplying the progress spread:", fg="cyan")
    bands = _apply_progress(site, registration, course, learners)
    click.secho(
        f"  no progress: {bands['none']}  part-way: {bands['partway']}  "
        f"complete: {bands['complete']}",
        fg="green",
    )

    click.secho("\nGranting object-level view_cohort:", fg="cyan")
    granted: list[str] = []
    for email in educator_email:
        educator = User.objects.filter(email=email).first()
        if educator is None:
            click.secho(f"  ! Educator '{email}' not found - skipped", fg="red")
            continue
        assign_perm("view_cohort", educator, cohort)
        granted.append(email)
        click.secho(f"  + {email}", fg="green")

    item_count = len(course.viewable_collection_items())
    member_count = CohortMembership.objects.filter(cohort=cohort, site=site).count()
    panel_path = (
        f"/educator/organisations/{organisation.slug}/cohorts/{cohort.pk}"
        "/__tabs/course_progress"
    )

    click.secho("\n--- Summary ---", fg="cyan", bold=True)
    click.secho(f"Site:          {site.name} ({site.domain})", fg="cyan")
    click.secho(f"Organisation:  {organisation.name} ({organisation.slug})", fg="cyan")
    click.secho(f"Course:        {course.title}  slug={COURSE_SLUG}", fg="cyan")
    click.secho(f"Items:         {item_count} (column pages of 15)", fg="cyan")
    click.secho(f"Cohort:        {cohort.name}  pk={cohort.pk}", fg="cyan")
    click.secho(f"Learners:      {member_count} (learner pages of 20)", fg="cyan")
    click.secho(
        f"Learner login: {LEARNER_EMAIL_TEMPLATE} / {LEARNER_PASSWORD}", fg="cyan"
    )
    click.secho(f"Granted to:    {granted}", fg="cyan")
    click.secho(
        f"Matrix:        http://{site.domain}{panel_path}", fg="cyan", bold=True
    )
