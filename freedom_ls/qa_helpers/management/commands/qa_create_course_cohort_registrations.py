"""Give one course enough cohort registrations to page its educator table.

The educator course page (``/educator/organisations/<org>/courses/<pk>``)
renders two independent paginators, ``CourseCohortRegistrationsPanel``
("Cohort Registrations") and ``CourseLearnerRegistrationsPanel`` ("Direct
Registrations"). The cohort one cannot be exercised on a stock dev database
because no ``CohortCourseRegistration`` row exists at all, so the table is
empty and its paginator never renders.

IMPORTANT -- what a row is. ``CourseCohortRegistrationDataTable`` paginates
``CohortCourseRegistration`` rows, i.e. **one row per registered cohort**. The
size of a cohort makes no difference: a cohort of five hundred learners is
still one row. Paging this table therefore needs many *cohorts* registered to
the course, not many learners in one cohort. The columns are Cohort / Active /
Registered -- no learner is rendered at all.

The page size is read off ``CourseCohortRegistrationDataTable.page_size``
rather than hardcoded, so this command keeps producing more than one page if
the table's own configuration changes.

Scaffolding cohorts are created empty and zero-padded (``QA Course Reg Cohort
01`` ...). Empty because a ``CohortCourseRegistration`` fans a ``CourseProgress``
record out to every active member of the cohort -- padding with populated
cohorts would write progress rows for learners a tester may be mid-assertion
on. Zero-padded because the table orders by ``cohort__name``, where an
unpadded ``10`` sorts before ``2`` and looks exactly like the skipped row a
pagination check is hunting for.

The requested count deliberately straddles a page boundary inside the padded
block, so both sides of the boundary are individually identifiable.

Idempotent: cohorts are matched on ``(site, organisation, name)`` and
registrations on the model's own ``unique_cohort_course_registration``
constraint, so re-running tops up rather than duplicating.

Usage:
    uv run python manage.py qa_create_course_cohort_registrations
    uv run python manage.py qa_create_course_cohort_registrations \
        --course-slug functionality-demo-show-end-with-topic \
        --num-registrations 8
"""

from typing import cast

import djclick as click

from django.contrib.sites.models import Site

from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.views import CourseCohortRegistrationDataTable
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
)
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.organisations.models import Organisation

DEFAULT_SITE_NAME = "DemoDev"
DEFAULT_ORGANISATION_SLUG = "demodev"
DEFAULT_COURSE_SLUG = "functionality-demo-show-end-with-topic"
DEFAULT_NUM_REGISTRATIONS = 8
DEFAULT_NAME_PREFIX = "QA Course Reg Cohort"
# Cohorts that already exist and already hold learners, so the table shows at
# least one registration a tester can click through to something populated.
# "Cohort 2025.03.04" is deliberately NOT in this list: it holds demodev_s1,
# and registering it would mint that persona a course-progress record.
DEFAULT_REUSE_COHORTS = ("QA Pagination Cohort", "Cohort 2025.04.06")


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e


def _get_organisation(slug: str, site: Site) -> Organisation:
    try:
        return Organisation._base_manager.get(slug=slug, site=site)
    except Organisation.DoesNotExist as e:
        available = list(
            Organisation._base_manager.filter(site=site).values_list("slug", flat=True)
        )
        raise click.ClickException(
            f"Organisation '{slug}' not found on site '{site.name}'. "
            f"Available: {available}"
        ) from e


def _get_course(slug: str, site: Site) -> Course:
    try:
        return Course._base_manager.get(slug=slug, site=site)
    except Course.DoesNotExist as e:
        raise click.ClickException(
            f"Course '{slug}' not found on site '{site.name}'."
        ) from e


def _cohort_name(prefix: str, index: int) -> str:
    """``QA Course Reg Cohort 07`` -- zero-padded so names sort like numbers."""
    return f"{prefix} {index:02d}"


def _ensure_cohort(name: str, organisation: Organisation, site: Site) -> Cohort:
    """Return the named cohort on this organisation, creating it if absent."""
    existing = Cohort._base_manager.filter(
        site=site, organisation=organisation, name=name
    ).first()
    if existing is not None:
        return existing
    return cast(Cohort, CohortFactory(name=name, organisation=organisation, site=site))


def _ensure_registration(
    cohort: Cohort, course: Course, site: Site
) -> tuple[CohortCourseRegistration, bool]:
    """Register the cohort for the course. True when a row was created."""
    existing = CohortCourseRegistration._base_manager.filter(
        site=site, cohort=cohort, course=course
    ).first()
    if existing is not None:
        return existing, False
    registration = cast(
        CohortCourseRegistration,
        CohortCourseRegistrationFactory(
            cohort=cohort, course=course, site=site, is_active=True
        ),
    )
    return registration, True


@click.command()
@click.option(
    "--site-name",
    default=DEFAULT_SITE_NAME,
    help=f"Site the data belongs to (default: '{DEFAULT_SITE_NAME}').",
)
@click.option(
    "--organisation-slug",
    default=DEFAULT_ORGANISATION_SLUG,
    help=f"Organisation owning the cohorts (default: '{DEFAULT_ORGANISATION_SLUG}').",
)
@click.option(
    "--course-slug",
    default=DEFAULT_COURSE_SLUG,
    help=f"Course to register cohorts to (default: '{DEFAULT_COURSE_SLUG}').",
)
@click.option(
    "--num-registrations",
    default=DEFAULT_NUM_REGISTRATIONS,
    type=int,
    help=(
        "Total cohort registrations the course should end up with "
        f"(default: {DEFAULT_NUM_REGISTRATIONS})."
    ),
)
@click.option(
    "--name-prefix",
    default=DEFAULT_NAME_PREFIX,
    help=f"Prefix for scaffolding cohort names (default: '{DEFAULT_NAME_PREFIX}').",
)
@click.option(
    "--reuse-cohort",
    "reuse_cohorts",
    multiple=True,
    default=DEFAULT_REUSE_COHORTS,
    help="Name of an existing cohort to register too. Repeatable.",
)
def command(
    site_name: str,
    organisation_slug: str,
    course_slug: str,
    num_registrations: int,
    name_prefix: str,
    reuse_cohorts: tuple[str, ...],
) -> None:
    """Register enough cohorts to a course that its educator table paginates."""
    site = _get_site(site_name)
    organisation = _get_organisation(organisation_slug, site)
    course = _get_course(course_slug, site)

    page_size = CourseCohortRegistrationDataTable.page_size
    if num_registrations <= page_size:
        raise click.ClickException(
            f"--num-registrations={num_registrations} would not page: "
            f"CourseCohortRegistrationDataTable.page_size is {page_size}. "
            f"Ask for at least {page_size + 1}."
        )

    before_registrations = CohortCourseRegistration._base_manager.filter(
        course=course
    ).count()
    before_progress = CourseProgress._base_manager.filter(course=course).count()

    created_rows: list[str] = []
    reused_rows: list[str] = []
    created_cohorts: list[str] = []

    for name in reuse_cohorts:
        cohort = Cohort._base_manager.filter(
            site=site, organisation=organisation, name=name
        ).first()
        if cohort is None:
            raise click.ClickException(
                f"--reuse-cohort '{name}' not found on organisation "
                f"'{organisation.slug}' / site '{site.name}'."
            )
        _, created = _ensure_registration(cohort, course, site)
        (created_rows if created else reused_rows).append(cohort.name)

    index = 1
    while (
        CohortCourseRegistration._base_manager.filter(course=course).count()
        < num_registrations
    ):
        name = _cohort_name(name_prefix, index)
        if not Cohort._base_manager.filter(
            site=site, organisation=organisation, name=name
        ).exists():
            created_cohorts.append(name)
        cohort = _ensure_cohort(name, organisation, site)
        _, created = _ensure_registration(cohort, course, site)
        (created_rows if created else reused_rows).append(cohort.name)
        index += 1

    registrations = (
        CohortCourseRegistration._base_manager.filter(course=course)
        .select_related("cohort")
        .order_by("cohort__name")
    )
    total = registrations.count()
    pages = -(-total // page_size)
    after_progress = CourseProgress._base_manager.filter(course=course).count()

    click.secho("\n--- Course cohort-registration pagination ---", fg="cyan", bold=True)
    click.secho(f"Site:         {site.name} ({site.domain}) [id {site.pk}]", fg="cyan")
    click.secho(
        f"Organisation: {organisation.name} [slug: {organisation.slug}]", fg="cyan"
    )
    click.secho(f"Course:       {course.title} [slug: {course.slug}]", fg="cyan")
    click.echo(f"              pk: {course.pk}")

    click.secho(
        f"\nCohorts created: {len(created_cohorts)}  "
        f"Registrations created: {len(created_rows)}  "
        f"Already present: {len(reused_rows)}",
        fg="green",
    )
    click.secho(
        f"Cohort registrations on this course: {before_registrations} -> {total}",
        fg="green",
        bold=True,
    )
    click.secho(
        f"page_size={page_size} (CourseCohortRegistrationDataTable) -> {pages} page(s)",
        fg="green" if pages > 1 else "red",
        bold=True,
    )
    click.secho(
        f"CourseProgress rows on this course (cohort fan-out): "
        f"{before_progress} -> {after_progress}",
        fg="yellow",
    )

    click.secho("\nRows in table order (ordered by cohort__name):", bold=True)
    for position, registration in enumerate(registrations, start=1):
        page_number = (position - 1) // page_size + 1
        members = CohortMembership._base_manager.filter(
            cohort=registration.cohort
        ).count()
        boundary = "  <- page break above" if position % page_size == 1 else ""
        click.echo(
            f"  p{page_number} #{position:>2}  {registration.cohort.name:<28} "
            f"active={registration.is_active}  members={members}{boundary}"
        )

    click.secho(
        f"\nEducator page: /educator/organisations/{organisation.slug}"
        f"/courses/{course.pk}",
        fg="green",
    )
