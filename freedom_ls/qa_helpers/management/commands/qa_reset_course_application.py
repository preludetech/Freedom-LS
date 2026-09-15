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
from freedom_ls.course_applications.models import CourseApplication
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
    """Delete a QA applicant's CourseApplication and the FormProgress it names."""
    site = _get_site(site_name)
    user: User | None = User.objects.filter(email=learner).first()
    if user is None:
        raise click.ClickException(f"No user with email '{learner}'.")
    course = _get_course(site, course_slug)

    click.secho("\n--- Reset course application ---", fg="cyan", bold=True)
    click.secho(f"Site:      {site.name} ({site.domain}) [id {site.pk}]", fg="cyan")
    click.secho(f"Applicant: {user.email} [pk {user.pk}]", fg="cyan", bold=True)
    click.secho(f"Course:    {course.slug}", fg="cyan")

    application: CourseApplication | None = CourseApplication._base_manager.filter(
        user=user, course=course
    ).first()
    if application is None:
        click.secho("\nNo application to withdraw. Nothing to do.", fg="yellow")
        return

    form_progress_pk = application.form_progress_id
    click.secho("\nWill remove:", fg="green", bold=True)
    click.echo(f"  CourseApplication {application.pk} ({user.email} / {course.slug})")

    file_paths: list[tuple[str, Storage]] = []
    if form_progress_pk is None:
        click.echo("  (this application names no FormProgress)")
    else:
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

    if dry_run:
        click.secho("\n--dry-run: nothing was deleted.", fg="yellow", bold=True)
        return

    click.secho(f"\nApplication deleted: {application.delete()}", fg="green", bold=True)
    if form_progress_pk is not None:
        # Re-fetched by pk now the RESTRICT no longer applies.
        deleted = FormProgress._base_manager.get(pk=form_progress_pk).delete()
        click.secho(f"Sitting deleted:     {deleted}", fg="green", bold=True)
        for name, storage in file_paths:
            click.echo(f"  upload {name} exists now: {storage.exists(name)}")

    click.secho("\nVerifying:", fg="cyan", bold=True)
    remaining = CourseApplication._base_manager.filter(user=user, course=course).count()
    click.echo(f"  applications for this user+course: {remaining}")
    if form_progress_pk is not None:
        click.echo(
            f"  sitting {form_progress_pk} still present: "
            f"{FormProgress._base_manager.filter(pk=form_progress_pk).exists()}"
        )
    click.secho(
        f"\n{user.email} can now apply to {course.slug} from scratch.", fg="green"
    )
