"""Withdraw a QA applicant's application to a course, plus the sitting it names.

Re-walking an application-gated flow from the start needs the persona back to
"never applied": the course detail page offers "Apply now" only while no
``CourseApplication`` exists for that (user, course), and a fresh apply mints a
brand-new ``FormProgress``.

Order is forced by the schema. ``CourseApplication.form_progress`` is a
``OneToOneField(on_delete=RESTRICT)``, so the application row must go first and
the sitting second -- deleting the sitting while the application still names it
raises ``RestrictedError``. This command re-fetches the sitting **by pk after**
the application is gone, so it never has to reason about the RESTRICT.

Note that even *inspecting* the blast radius trips the restriction: building a
``Collector`` over the sitting while the application stands raises rather than
reporting. That is why the preview below lists counts it queried directly
instead of collecting.

Deleting the sitting cascades to its ``QuestionAnswer`` rows (and their selected
options and ``QuestionAnswerFile`` rows). ``QuestionAnswerFile`` has a
``post_delete`` receiver that removes the stored upload, so the file really does
leave storage -- the paths are printed before the delete, since afterwards there
is no row left to ask.

``LearnerCourseRegistration``, ``CourseProgress`` and ``TopicProgress`` are never
touched: an application sitting is started outside the course player, so it has
no ``CourseFormAttempt`` and no bearing on topic completion or sequential unlock.

Idempotent: with no application in scope it reports that and exits 0.

Usage:
    uv run python manage.py qa_reset_course_application \
        --learner qa.applicant.a@email.com \
        --course-slug functionality-demo-application-gated-course --dry-run
"""

import djclick as click

from django.contrib.sites.models import Site
from django.core.files.storage import Storage

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.course_applications.erasure import erase_anonymous_applicant
from freedom_ls.course_applications.models import AnonymousApplicant, CourseApplication
from freedom_ls.form_engine.models import (
    FormProgress,
    QuestionAnswer,
    QuestionAnswerFile,
)


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e


def _get_course(site: Site, course_slug: str) -> Course:
    course: Course | None = Course.objects.filter(slug=course_slug, site=site).first()
    if course is None:
        raise click.ClickException(
            f"Course '{course_slug}' not found on site '{site.name}'."
        )
    return course


def _erase_anonymous_applicants(
    email: str, course: Course, site: Site, dry_run: bool
) -> None:
    """Erase the unverified applicants for this address and course on the site.

    _base_manager: outside a request there is no ambient site to filter on, so
    the site is named here instead.
    """
    applicants = AnonymousApplicant._base_manager.filter(
        email=email, course=course, site=site, user__isnull=True
    )
    for applicant in applicants:
        if dry_run:
            click.echo(f"  would erase AnonymousApplicant {applicant.pk}")
            continue
        erase_anonymous_applicant(applicant)
        click.secho(f"Erased AnonymousApplicant {applicant.pk}", fg="green", bold=True)


def _preview_application(application: CourseApplication) -> list[tuple[str, Storage]]:
    """Print what withdrawing this application removes; return its upload paths.

    The paths are read now because once the rows are gone nothing names them.
    """
    click.echo(f"  CourseApplication {application.pk} ({application.applicant_email})")
    file_paths: list[tuple[str, Storage]] = []
    form_progress_pk = application.form_progress_id
    if form_progress_pk is None:
        click.echo("  (this application names no FormProgress)")
        return file_paths
    form_progress = FormProgress._base_manager.select_related("form").get(
        pk=form_progress_pk
    )
    answer_count = QuestionAnswer._base_manager.filter(
        form_progress=form_progress
    ).count()
    answer_files = QuestionAnswerFile._base_manager.filter(
        answer__form_progress=form_progress
    )
    for answer_file in answer_files:
        if answer_file.file.name:
            file_paths.append((answer_file.file.name, answer_file.file.storage))
    click.echo(
        f"  FormProgress {form_progress.pk} | {form_progress.form.title!r} | "
        f"completed={form_progress.completed_time} | answers={answer_count}"
    )
    for name, storage in file_paths:
        click.echo(f"    upload {name} (exists={storage.exists(name)})")
    return file_paths


def _withdraw_application(application: CourseApplication) -> None:
    """Delete the application, then the sitting it named.

    A claimed application is deleted through its applicant row, which cascades
    to it: left behind, that row would say the address had applied and claimed
    when nothing of the application remains.
    """
    form_progress_pk = application.form_progress_id
    file_paths = _preview_application(application)
    if application.anonymous_applicant_id is not None:
        deleted = AnonymousApplicant._base_manager.filter(
            pk=application.anonymous_applicant_id
        ).delete()
    else:
        deleted = application.delete()
    click.secho(f"Application deleted: {deleted}", fg="green", bold=True)
    if form_progress_pk is not None:
        # Re-fetched by pk now the RESTRICT no longer applies.
        deleted = FormProgress._base_manager.get(pk=form_progress_pk).delete()
        click.secho(f"Sitting deleted:     {deleted}", fg="green", bold=True)
        for name, storage in file_paths:
            click.echo(f"  upload {name} exists now: {storage.exists(name)}")


@click.command()
@click.option("--learner", required=True, help="Email address of the QA applicant.")
@click.option(
    "--course-slug", required=True, help="Slug of the application-gated course."
)
@click.option(
    "--site-name",
    default="DemoDev",
    help="Site name the applicant and course live on (default: 'DemoDev').",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be deleted without deleting it.",
)
def command(learner: str, course_slug: str, site_name: str, dry_run: bool) -> None:
    """Delete a QA applicant's CourseApplications and the FormProgress each names.

    An applicant who never followed the claim link has no User; their anonymous
    applications are erased all the same. An account may hold more than one
    application to the course once it has claimed one, so every one goes.
    """
    site = _get_site(site_name)
    email = learner.strip().lower()
    course = _get_course(site, course_slug)
    user: User | None = User._base_manager.filter(email__iexact=email).first()

    click.secho("\n--- Reset course application ---", fg="cyan", bold=True)
    click.secho(f"Site:      {site.name} ({site.domain}) [id {site.pk}]", fg="cyan")
    click.secho(
        f"Applicant: {email}"
        + (f" [User pk {user.pk}]" if user is not None else " (no account)"),
        fg="cyan",
        bold=True,
    )
    click.secho(f"Course:    {course.slug}", fg="cyan")

    applications = list(
        CourseApplication._base_manager.filter(user=user, course=course)
        if user is not None
        else CourseApplication._base_manager.none()
    )
    if not applications:
        click.secho("\nNo application to withdraw for this account.", fg="yellow")

    if dry_run:
        click.secho("\nWould remove:", fg="green", bold=True)
        for application in applications:
            _preview_application(application)
        _erase_anonymous_applicants(email, course, site, dry_run)
        click.secho("\n--dry-run: nothing was deleted.", fg="yellow", bold=True)
        return

    click.secho("\nRemoving:", fg="green", bold=True)
    for application in applications:
        _withdraw_application(application)
    _erase_anonymous_applicants(email, course, site, dry_run)

    click.secho("\nVerifying:", fg="cyan", bold=True)
    remaining = (
        CourseApplication._base_manager.filter(user=user, course=course).count()
        if user is not None
        else 0
    )
    click.echo(f"  applications for this account+course: {remaining}")
    click.echo(
        "  anonymous applicants left for this address+course: "
        f"{AnonymousApplicant._base_manager.filter(email=email, course=course, site=site).count()}"
    )
    click.secho(f"\n{email} can now apply to {course.slug} from scratch.", fg="green")
