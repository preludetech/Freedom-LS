"""Seed a dedicated cohort + course where BOTH course-progress paginators are live.

The educator course-progress panel (``CohortCourseProgressPanel``) runs two
independent paginators: columns over the flat course items (Topic + Form,
CourseParts excluded) at ``COLUMN_PAGE_SIZE`` (15), and rows over
``CohortMembership`` at ``LEARNER_PAGE_SIZE`` (20). Exercising the interaction
between them — paging the columns while holding the learner page — needs a
course with >15 items AND a cohort with >20 members at the same time.

This command builds that pair on a course of its own so the demo courses (and
any learner progress QA running against them) are left untouched. Item padding
is delegated to ``qa_add_course_items_for_pagination``.

Idempotent.
"""

from typing import cast

import djclick as click
from guardian.shortcuts import assign_perm

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.db.models import Max

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
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
from freedom_ls.organisations.utils import get_default_organisation

COURSE_SLUG = "qa-column-pagination-course"
COURSE_TITLE = "QA Column Pagination Course"
COHORT_NAME = "QA Column Pagination Cohort"
LEARNER_EMAIL_TEMPLATE = "qa_colpag_learner_{index}@example.com"
SEED_TOPIC_COUNT = 3


def _ensure_course(site: Site) -> Course:
    course: Course | None = Course.objects.filter(slug=COURSE_SLUG, site=site).first()
    if course is None:
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
    else:
        click.secho(f"Reusing course '{course.title}' ({COURSE_SLUG})", fg="yellow")

    course_ctype = ContentType.objects.get_for_model(Course)
    topic_ctype = ContentType.objects.get_for_model(Topic)

    for index in range(1, SEED_TOPIC_COUNT + 1):
        slug = f"{COURSE_SLUG}-lesson-{index:02d}"
        topic: Topic | None = Topic.objects.filter(slug=slug, site=site).first()
        if topic is None:
            topic = cast(
                Topic,
                TopicFactory(
                    title=f"Column Pagination Lesson {index:02d}", slug=slug, site=site
                ),
            )
        linked = ContentCollectionItem.objects.filter(
            collection_type=course_ctype,
            collection_id=course.pk,
            child_type=topic_ctype,
            child_id=topic.pk,
            site=site,
        ).exists()
        if not linked:
            next_order = (
                ContentCollectionItem.objects.filter(
                    collection_type=course_ctype, collection_id=course.pk, site=site
                ).aggregate(Max("order"))["order__max"]
                or 0
            ) + 1
            ContentCollectionItemFactory(
                collection_object=course,
                child_object=topic,
                order=next_order,
                site=site,
            )
            click.secho(f"  + Linked seed topic '{topic.title}'", fg="green")
    return course


def _ensure_cohort(site: Site, course: Course, num_learners: int) -> Cohort:
    cohort: Cohort | None = Cohort.objects.filter(name=COHORT_NAME, site=site).first()
    if cohort is None:
        cohort = cast(
            Cohort,
            CohortFactory(
                name=COHORT_NAME, site=site, organisation=get_default_organisation(site)
            ),
        )
        click.secho(f"Created cohort '{COHORT_NAME}'", fg="green")
    else:
        click.secho(f"Reusing cohort '{COHORT_NAME}'", fg="yellow")

    added = 0
    for index in range(1, num_learners + 1):
        email = LEARNER_EMAIL_TEMPLATE.format(index=index)
        user: User | None = User.objects.filter(email=email).first()
        if user is None:
            user = cast(
                User,
                UserFactory(
                    email=email,
                    first_name="Colpag",
                    last_name=f"Learner {index:02d}",
                    is_active=True,
                    password="testpass123",  # noqa: S106  # pragma: allowlist secret
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
    click.secho(f"Cohort members added this run: {added}", fg="green")

    if not CohortCourseRegistration.objects.filter(
        cohort=cohort, course=course, site=site
    ).exists():
        CohortCourseRegistrationFactory(cohort=cohort, course=course, site=site)
        click.secho(f"Registered cohort for '{course.title}'", fg="green")
    else:
        click.secho(f"Cohort already registered for '{course.title}'", fg="yellow")
    return cohort


@click.command()
@click.argument("site_name", default="DemoDev")
@click.option(
    "--num-learners",
    default=22,
    type=int,
    help="Cohort size; must exceed 20 for the learner paginator (default: 22).",
)
@click.option(
    "--target-item-count",
    default=18,
    type=int,
    help="Flat course items; must exceed 15 for the column paginator (default: 18).",
)
@click.option(
    "--educator-email",
    multiple=True,
    default=("qa-educator-progress@example.com", "demodev@email.com"),
    help="Educator(s) to grant object-level view_cohort on the cohort.",
)
def command(
    site_name: str,
    num_learners: int,
    target_item_count: int,
    educator_email: tuple[str, ...],
) -> None:
    """Seed a cohort + course where both course-progress paginators paginate.

    SITE_NAME is the name of the site to seed (e.g. 'DemoDev').
    """
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e

    course = _ensure_course(site)

    click.secho("\nPadding course items:", fg="cyan")
    call_command(
        "qa_add_course_items_for_pagination",
        site_name,
        f"--course-slug={COURSE_SLUG}",
        f"--target-item-count={target_item_count}",
    )

    click.secho("\nBuilding cohort:", fg="cyan")
    cohort = _ensure_cohort(site, course, num_learners)

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

    # Re-query: Course.viewable_items() is memoized per instance.
    fresh_course = Course.objects.get(pk=course.pk)
    item_count = len(fresh_course.viewable_items())
    member_count = CohortMembership.objects.filter(cohort=cohort, site=site).count()

    click.secho("\n--- Summary ---", fg="cyan", bold=True)
    click.secho(f"Site:        {site.name} ({site.domain})", fg="cyan")
    click.secho(f"Course:      {fresh_course.title}  slug={COURSE_SLUG}", fg="cyan")
    click.secho(f"Items:       {item_count} (column pages of 15)", fg="cyan")
    click.secho(f"Cohort:      {cohort.name}  pk={cohort.pk}", fg="cyan")
    click.secho(f"Learners:    {member_count} (learner pages of 20)", fg="cyan")
    click.secho(f"Granted to:  {granted}", fg="cyan")
    click.secho(
        f"Matrix:      /educator/cohorts/{cohort.pk}/__tabs/course_progress",
        fg="cyan",
    )
