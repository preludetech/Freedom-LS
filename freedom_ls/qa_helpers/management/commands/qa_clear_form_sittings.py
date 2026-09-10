"""Clear a QA learner's form sittings at specific placements, safely.

Browser QA of the form runner leaves a sitting behind at every placement the
tester walked, and there is no UI route to clear one. Two different tables have
to go or the two surfaces disagree:

* the **start screen** button is chosen by ``form_start_page_buttons`` from the
  learner's ``FormProgress`` for that form -- "Continue Form" / "Try Again" /
  "Next" / "Finish Course", and only "Start Form" when there is no sitting;
* the **outline** status is chosen by ``get_content_status`` from the
  ``CourseFormAttempt`` rows at that ``ContentCollectionItem``.

Deleting the ``FormProgress`` takes the attempt with it (the join is a
OneToOne CASCADE), so this command deletes sittings and reports the attempts
that went with them.

Unlike ``qa_reset_learner_progress`` this is **placement-scoped and refuses to
touch a sitting that a CourseApplication names**. ``CourseApplication.form_progress``
is RESTRICT, so a blanket reset aborts for any persona holding an application;
here such sittings are skipped and listed instead. ``TopicProgress`` and
``CourseProgress`` are never touched, so topic completions -- and the sequential
unlocking that makes a mid-course form reachable -- survive.

Note that clearing a form can still re-lock what follows it: an item after the
form that has no progress row of its own was only READY because the form was
complete. Items that hold their own completed progress stay COMPLETE. The
printed outline shows exactly which, so check it rather than guessing.

Usage:
    uv run python manage.py qa_clear_form_sittings --learner qa_applicant@email.com \
        --course-slug functionality-demo-show-end-with-quiz --item-title "Mid course Quiz"

    uv run python manage.py qa_clear_form_sittings --learner qa_applicant@email.com \
        --course-slug functionality-demo-show-end-with-topic --dry-run
"""

import djclick as click

from django.contrib.sites.models import Site

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.form_engine.models import Form, FormProgress
from freedom_ls.learner_interface.utils import get_course_index
from freedom_ls.learner_progress.models import CourseFormAttempt


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e


def _get_courses(site: Site, course_slugs: tuple[str, ...]) -> list[Course]:
    """Resolve the requested course slugs, or every course on the site."""
    if not course_slugs:
        return list(Course.objects.filter(site=site))
    courses: list[Course] = []
    for slug in course_slugs:
        course: Course | None = Course.objects.filter(slug=slug, site=site).first()
        if course is None:
            raise click.ClickException(
                f"Course '{slug}' not found on site '{site.name}'."
            )
        courses.append(course)
    return courses


def _target_attempts(
    user: User, courses: list[Course], item_titles: tuple[str, ...]
) -> list[CourseFormAttempt]:
    """The learner's attempts at the form placements in scope.

    Filtering is on ``collection_item``, not on the form: one form placed twice
    in a course is two placements, sat separately, and only the named one
    should be cleared.
    """
    wanted_titles = {title.casefold() for title in item_titles}
    attempts: list[CourseFormAttempt] = []
    for course in courses:
        placements = [
            item
            for item in course.viewable_collection_items()
            if isinstance(item.child, Form)
            and (not wanted_titles or item.child.title.casefold() in wanted_titles)
        ]
        if not placements:
            continue
        attempts.extend(
            CourseFormAttempt.objects.filter(
                course_progress__learner__user=user,
                course_progress__course=course,
                collection_item__in=[item.id for item in placements],
            ).select_related("form_progress__form", "collection_item")
        )
    return attempts


@click.command()
@click.option("--learner", required=True, help="Email address of the QA learner.")
@click.option(
    "--course-slug",
    "course_slugs",
    multiple=True,
    help="Restrict to these courses (repeatable). Default: every course on the site.",
)
@click.option(
    "--item-title",
    "item_titles",
    multiple=True,
    help="Only clear placements with these item titles (repeatable, case-insensitive).",
)
@click.option(
    "--keep-pk",
    "keep_pks",
    multiple=True,
    help="FormProgress pk(s) to leave alone regardless of scope (repeatable).",
)
@click.option(
    "--site-name",
    default="DemoDev",
    help="Site name the learner and courses live on (default: 'DemoDev').",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be deleted without deleting it.",
)
def command(
    learner: str,
    course_slugs: tuple[str, ...],
    item_titles: tuple[str, ...],
    keep_pks: tuple[str, ...],
    site_name: str,
    dry_run: bool,
) -> None:
    """Delete a QA learner's sittings at named form placements."""
    site = _get_site(site_name)
    user: User | None = User.objects.filter(email=learner).first()
    if user is None:
        raise click.ClickException(f"No user with email '{learner}'.")

    courses = _get_courses(site, course_slugs)
    attempts = _target_attempts(user, courses, item_titles)

    keep = {pk.strip() for pk in keep_pks}
    to_delete: list[FormProgress] = []
    skipped: list[tuple[FormProgress, str]] = []
    for attempt in attempts:
        form_progress = attempt.form_progress
        application: CourseApplication | None = CourseApplication._base_manager.filter(
            form_progress=form_progress
        ).first()
        if application is not None:
            skipped.append(
                (form_progress, f"named by CourseApplication {application.pk}")
            )
        elif str(form_progress.pk) in keep:
            skipped.append((form_progress, "--keep-pk"))
        else:
            to_delete.append(form_progress)

    click.secho("\n--- Clear form sittings ---", fg="cyan", bold=True)
    click.secho(f"Site:    {site.name} ({site.domain}) [id {site.pk}]", fg="cyan")
    click.secho(f"Learner: {user.email} [pk {user.pk}]", fg="cyan", bold=True)
    click.secho(
        "Scope:   "
        + ", ".join(course.slug for course in courses)
        + (
            f" | items: {', '.join(item_titles)}"
            if item_titles
            else " | all form items"
        ),
        fg="cyan",
    )

    if not to_delete and not skipped:
        click.secho("No sittings found in scope. Nothing to do.", fg="yellow")
        return

    verb = "Would delete" if dry_run else "Deleting"
    click.secho(f"\n{verb} {len(to_delete)} sitting(s):", fg="green", bold=True)
    for form_progress in to_delete:
        attempt_pks = [
            str(pk)
            for pk in CourseFormAttempt.objects.filter(
                form_progress=form_progress
            ).values_list("pk", flat=True)
        ]
        click.echo(
            f"  FormProgress {form_progress.pk} | {form_progress.form.title!r} | "
            f"completed={form_progress.completed_time} | scores={form_progress.scores} | "
            f"attempts={attempt_pks}"
        )

    if skipped:
        click.secho(f"\nSkipped {len(skipped)} sitting(s):", fg="yellow", bold=True)
        for form_progress, reason in skipped:
            click.echo(
                f"  FormProgress {form_progress.pk} | {form_progress.form.title!r} | {reason}"
            )

    if dry_run:
        click.secho("\n--dry-run: nothing was deleted.", fg="yellow", bold=True)
        return

    deleted = FormProgress.objects.filter(
        pk__in=[form_progress.pk for form_progress in to_delete]
    ).delete()
    click.secho(f"\nDeleted: {deleted}", fg="green", bold=True)

    click.secho("\nOutline now reads:", fg="cyan", bold=True)
    for course in courses:
        entries = get_course_index(user, course, can_access_content=True)
        if not entries:
            continue
        click.secho(f"  {course.slug}", fg="cyan")
        for entry in entries:
            click.echo(f"    {entry.get('title')} -> {entry.get('status')}")
