"""Add filler courses to a dashboard category so its section spans 3+ pages.

``qa_create_dashboard_paging_fixtures`` Seed A takes "Start here" to six
courses, which at ``SECTION_PAGE_SIZE`` (3) is exactly **two** pages. Two pages
is not enough to exercise the dashboard's focus-management component:
``courseSectionPagination``
(``freedom_ls/learner_interface/static/learner_interface/js/alpine-components.js``)
re-focuses the arrow that was pressed *if it is still live*, and falls back to
the section ``<h2>`` when that arrow has become ``aria-disabled``. With two
pages every paging action lands on a boundary page, so the pressed arrow is
always disabled afterwards and only the fallback branch can ever run.

A third page fixes that: pressing next from page one lands on page two, where
both arrows are live, so focus returns to the next arrow -- the primary branch,
and the main accessibility assertion of the QA plan's section 8.1.

The courses are built by ``_ensure_pagination_course`` imported from
``qa_create_dashboard_paging_fixtures``, so they are identical in every respect
to the existing ``Pagination A``-``D`` fixtures: published, free, one Topic,
``dashboard_category`` set to the category *and* the same row in the
``categories`` m2m. Cross-command imports inside ``qa_helpers`` are the
established convention here.

Deliberately NOT added to that command's ``PAGINATION_LETTERS``: Seed B
registers ``demodev_paging`` on every letter in that list and indexes
``PAGING_REGISTERED_DAYS_AGO`` by slug, so extending it would both break Seed B
and give these courses the registrations they are meant not to have. These are
discovery-only fixtures -- no registrations, no recommendations, no progress.

Idempotent: ``_ensure_pagination_course`` matches on ``(slug, site)``.

Usage:
    uv run python manage.py qa_extend_start_here_section
    uv run python manage.py qa_extend_start_here_section DemoDev --letters E,F,G
"""

import djclick as click

from django.contrib.sites.models import Site

from freedom_ls.content_engine.models import Course, CourseCategory
from freedom_ls.course_recommendations.models import RecommendedCourse
from freedom_ls.learner_interface.dashboard_sections import SECTION_PAGE_SIZE
from freedom_ls.learner_management.models import LearnerCourseRegistration
from freedom_ls.qa_helpers.management.commands.qa_create_dashboard_paging_fixtures import (
    _ensure_pagination_course,
    _get_category,
    _get_site,
)

DEFAULT_LETTERS = "E,F,G"


def _parse_letters(raw: str) -> list[str]:
    letters = [part.strip().upper() for part in raw.split(",") if part.strip()]
    if not letters:
        raise click.ClickException("No letters given.")
    bad = [letter for letter in letters if not letter.isalpha() or len(letter) != 1]
    if bad:
        raise click.ClickException(f"Not single letters: {bad}")
    return letters


def _describe(course: Course) -> str:
    category = course.dashboard_category
    return (
        f"  {course.title:<14} slug={course.slug:<14} "
        f"visibility={course.visibility:<10} "
        f"access_config={course.access_config} "
        f"dashboard_category={category.slug if category else None} "
        f"categories={[c.slug for c in course.categories.all()]} "
        f"items={len(course.viewable_items())}"
    )


@click.command()
@click.argument("site_name", default="DemoDev")
@click.option(
    "--category-slug",
    default="start-here",
    show_default=True,
    help="CourseCategory whose dashboard section should grow.",
)
@click.option(
    "--letters",
    default=DEFAULT_LETTERS,
    show_default=True,
    help="Comma-separated Pagination letters to ensure, e.g. 'E,F,G'.",
)
def command(site_name: str, category_slug: str, letters: str) -> None:
    """Top a dashboard category up with Pagination filler courses.

    SITE_NAME is the site to create data on (default: DemoDev).
    """
    site: Site = _get_site(site_name)
    if category_slug != "start-here":
        # _get_category is hardcoded to the module's CATEGORY_SLUG.
        category = CourseCategory._base_manager.filter(
            slug=category_slug, site=site
        ).first()
        if category is None:
            raise click.ClickException(
                f"CourseCategory '{category_slug}' not found on site '{site.name}'."
            )
    else:
        category = _get_category(site)

    wanted = _parse_letters(letters)
    before = Course._base_manager.filter(site=site, dashboard_category=category).count()

    click.secho(
        f"\n--- Extending the '{category.title}' dashboard section ---",
        fg="cyan",
        bold=True,
    )
    click.secho(f"Site: {site.name} ({site.domain}) [id {site.pk}]", fg="cyan")

    courses = [_ensure_pagination_course(site, category, letter) for letter in wanted]
    for course in courses:
        click.secho(_describe(course), fg="green")

    # These are discovery-only fixtures: assert the two things the brief
    # excluded rather than trusting that nothing else attached them.
    for course in courses:
        registrations = LearnerCourseRegistration._base_manager.filter(
            course=course
        ).count()
        recommendations = RecommendedCourse._base_manager.filter(course=course).count()
        colour = "green" if registrations == recommendations == 0 else "red"
        click.secho(
            f"  {course.slug}: {registrations} registration(s), "
            f"{recommendations} recommendation(s)",
            fg=colour,
        )

    in_category = Course._base_manager.filter(
        site=site, dashboard_category=category
    ).order_by("title")
    total = in_category.count()
    pages = -(-total // SECTION_PAGE_SIZE)

    click.secho(
        f"\nCourses with dashboard_category='{category.slug}': {before} -> {total}",
        fg="green",
        bold=True,
    )
    click.secho(
        f"SECTION_PAGE_SIZE={SECTION_PAGE_SIZE} -> {pages} page(s)"
        + ("  <- a middle page exists" if pages >= 3 else "  <- no middle page"),
        fg="green" if pages >= 3 else "yellow",
        bold=True,
    )
    for position, course in enumerate(in_category, start=1):
        page_number = (position - 1) // SECTION_PAGE_SIZE + 1
        click.echo(f"  p{page_number} #{position} {course.title} ({course.slug})")
