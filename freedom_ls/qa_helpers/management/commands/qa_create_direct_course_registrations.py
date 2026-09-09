"""Top a course up with individual registrations so its educator table pages.

Companion to ``qa_create_course_cohort_registrations``. The educator course page
renders two independent paginators; that command feeds "Cohort Registrations",
this one feeds "Direct Registrations"
(``CourseLearnerRegistrationDataTable``, ``freedom_ls/educator_interface/views.py``).

Rows here are ``LearnerCourseRegistration`` -- **individual** grants, not
cohort-granted ones. A cohort registration does mint a ``CourseProgress`` per
member, but it creates no ``LearnerCourseRegistration``, so it never puts a row
in this table. The two tables are fed by genuinely different records.

Two things decide what the tester sees, and neither is the email address:

* ``get_queryset`` filters ``learner__organisation=request.organisation``, so a
  registration only appears under the organisation slug in the URL.
* it orders by ``learner__user__first_name`` then ``last_name``. The email is
  merely a column. Scaffolding learners therefore share one ``first_name`` and
  carry a zero-padded ``last_name``, which is what makes their order in the
  table predictable and the page boundary unambiguous.

Page size is read off ``CourseLearnerRegistrationDataTable.page_size`` (the
``DataTable`` base default) rather than hardcoded.

Idempotent: users are matched on email and registrations on
``(learner, course, site)``, so re-running tops up rather than duplicating. The
target is a row count for the whole table, so registrations that already exist
-- including personas this fixture did not create -- count towards it and are
never modified.

Usage:
    uv run python manage.py qa_create_direct_course_registrations
    uv run python manage.py qa_create_direct_course_registrations DemoDev \
        --course-slug functionality-demo-show-end-with-topic --num-rows 8
"""

import djclick as click

from django.contrib.sites.models import Site

from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.views import CourseLearnerRegistrationDataTable
from freedom_ls.learner_management.models import LearnerCourseRegistration
from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.qa_helpers.management.commands.qa_create_dashboard_paging_fixtures import (
    _get_or_create_user,
    _get_site,
    _register,
)

DEFAULT_COURSE_SLUG = "functionality-demo-show-end-with-topic"
DEFAULT_NUM_ROWS = 8
DEFAULT_EMAIL_PREFIX = "qa_directreg"
#: Shared first name, so the padded last names alone decide the table order.
DEFAULT_FIRST_NAME = "QA DirectReg"


def _get_course(site: Site, slug: str) -> Course:
    course: Course | None = Course._base_manager.filter(slug=slug, site=site).first()
    if course is None:
        raise click.ClickException(f"Course '{slug}' not found on site '{site.name}'.")
    return course


def _rows(course: Course, organisation: Organisation):
    """The queryset the panel renders, in the order it renders it."""
    return (
        LearnerCourseRegistration._base_manager.filter(
            course=course, learner__organisation=organisation
        )
        .select_related("learner__user")
        .order_by("learner__user__first_name", "learner__user__last_name")
    )


@click.command()
@click.argument("site_name", default="DemoDev")
@click.option(
    "--course-slug",
    default=DEFAULT_COURSE_SLUG,
    show_default=True,
    help="Course whose Direct Registrations table should page.",
)
@click.option(
    "--num-rows",
    default=DEFAULT_NUM_ROWS,
    type=int,
    show_default=True,
    help="Total rows the table should end up with, existing ones included.",
)
@click.option(
    "--email-prefix",
    default=DEFAULT_EMAIL_PREFIX,
    show_default=True,
    help="Email prefix for the scaffolding learners.",
)
@click.option(
    "--first-name",
    default=DEFAULT_FIRST_NAME,
    show_default=True,
    help="Shared first name; the table sorts on this before last name.",
)
def command(
    site_name: str,
    course_slug: str,
    num_rows: int,
    email_prefix: str,
    first_name: str,
) -> None:
    """Add neutral learners with direct registrations until the table pages.

    SITE_NAME is the site to create data on (default: DemoDev).
    """
    site = _get_site(site_name)
    organisation = get_default_organisation(site)
    course = _get_course(site, course_slug)

    page_size = CourseLearnerRegistrationDataTable.page_size
    if num_rows <= page_size:
        raise click.ClickException(
            f"--num-rows={num_rows} would not page: "
            f"CourseLearnerRegistrationDataTable.page_size is {page_size}. "
            f"Ask for at least {page_size + 1}."
        )

    before = _rows(course, organisation).count()
    preserved = [r.learner.user.email for r in _rows(course, organisation)]

    created: list[str] = []
    reused: list[str] = []
    index = 1
    while _rows(course, organisation).count() < num_rows:
        email = f"{email_prefix}_{index:02d}@example.com"
        existed = LearnerCourseRegistration._base_manager.filter(
            course=course, learner__user__email=email
        ).exists()
        user = _get_or_create_user(site, email, first_name, f"{index:02d}")
        _register(user, course, site)
        (reused if existed else created).append(email)
        index += 1
        if index > num_rows + 50:
            raise click.ClickException("Row count is not rising; aborting.")

    rows = _rows(course, organisation)
    total = rows.count()
    pages = -(-total // page_size)

    click.secho("\n--- Direct-registration pagination ---", fg="cyan", bold=True)
    click.secho(f"Site:         {site.name} ({site.domain}) [id {site.pk}]", fg="cyan")
    click.secho(
        f"Organisation: {organisation.name} [slug: {organisation.slug}]", fg="cyan"
    )
    click.secho(f"Course:       {course.title} [slug: {course.slug}]", fg="cyan")
    click.echo(f"              pk: {course.pk}")
    click.secho(
        f"\nPre-existing rows left untouched: {before} ({', '.join(preserved)})",
        fg="cyan",
    )
    click.secho(
        f"Registrations created: {len(created)}  Already present: {len(reused)}",
        fg="green",
    )
    click.secho(f"Rows in this table: {before} -> {total}", fg="green", bold=True)
    click.secho(
        f"page_size={page_size} (CourseLearnerRegistrationDataTable) -> {pages} page(s)",
        fg="green" if pages > 1 else "red",
        bold=True,
    )

    click.secho(
        "\nRows in table order (first_name, then last_name):",
        bold=True,
    )
    for position, registration in enumerate(rows, start=1):
        page_number = (position - 1) // page_size + 1
        user = registration.learner.user
        boundary = "  <- page break above" if position % page_size == 1 else ""
        click.echo(
            f"  p{page_number} #{position}  {user.first_name!r:<16} "
            f"{user.last_name!r:<6} {user.email:<32} "
            f"active={registration.is_active}{boundary}"
        )

    click.secho(
        f"\nEducator page: /educator/organisations/{organisation.slug}"
        f"/courses/{course.pk}",
        fg="green",
    )
    if created:
        click.secho(
            f"Logins (password == email): {email_prefix}_NN@example.com", fg="green"
        )
