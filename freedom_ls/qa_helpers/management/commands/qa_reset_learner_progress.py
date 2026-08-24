"""Reset a QA learner's progress so a fixture course can be walked again.

Browser QA of the quiz runner leaves ``FormProgress`` rows behind (one per
attempt, plus half-finished ones), which changes what the start screen offers
("Continue Form" / "Next" / "Try Again" instead of "Start Form") and unlocks
items that a later run needs to see BLOCKED. There is no UI route to clear
them, so this command does it.

By default only form attempts are deleted, which keeps topic completions - and
therefore the sequential unlocking that makes a mid-course quiz reachable -
intact. ``--include-topics`` additionally clears topic progress, and
``CourseProgress`` rows are reset (not deleted: they are the learner's
registration-side record) to a freshly-registered state.

Scope it with ``--course-slug`` (repeatable). With no ``--course-slug`` the
learner's progress is cleared everywhere, so pass one when other fixtures rely
on this learner's data.

Usage:
    uv run python manage.py qa_reset_learner_progress --learner demodev_quizqa@email.com
    uv run python manage.py qa_reset_learner_progress \
        --learner demodev_quizqa@email.com \
        --course-slug qa-progression-block-course --include-topics
"""

from collections import Counter

import djclick as click

from django.contrib.sites.models import Site

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course, Topic
from freedom_ls.form_engine.models import Form, FormProgress
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e


def _get_courses(site: Site, course_slugs: tuple[str, ...]) -> list[Course] | None:
    """Resolve the requested course slugs, or None meaning "every course"."""
    if not course_slugs:
        return None
    courses: list[Course] = []
    for slug in course_slugs:
        course: Course | None = Course.objects.filter(slug=slug, site=site).first()
        if course is None:
            raise click.ClickException(
                f"Course '{slug}' not found on site '{site.name}'."
            )
        courses.append(course)
    return courses


def _course_items(courses: list[Course]) -> tuple[list[Form], list[Topic]]:
    """Split the viewable items of the given courses into forms and topics."""
    forms: list[Form] = []
    topics: list[Topic] = []
    for course in courses:
        for item in course.viewable_items():
            if isinstance(item, Form):
                forms.append(item)
            elif isinstance(item, Topic):
                topics.append(item)
    return forms, topics


@click.command()
@click.option("--learner", required=True, help="Email address of the QA learner.")
@click.option(
    "--course-slug",
    "course_slugs",
    multiple=True,
    help="Restrict the reset to these courses (repeatable). Default: all courses.",
)
@click.option(
    "--include-topics",
    is_flag=True,
    default=False,
    help="Also delete topic progress (default: form attempts only).",
)
@click.option(
    "--site-name",
    default="DemoDev",
    help="Site name the learner and courses live on (default: 'DemoDev').",
)
def command(
    learner: str,
    course_slugs: tuple[str, ...],
    include_topics: bool,
    site_name: str,
) -> None:
    """Delete a QA learner's quiz/form attempts so the fixtures can be re-walked."""
    site = _get_site(site_name)
    user: User | None = User.objects.filter(email=learner).first()
    if user is None:
        raise click.ClickException(f"No user with email '{learner}'.")

    courses = _get_courses(site, course_slugs)

    form_progress = FormProgress.objects.filter(user=user)
    topic_progress = TopicProgress.objects.filter(user=user)
    course_progress = CourseProgress.objects.filter(user=user)

    if courses is not None:
        forms, topics = _course_items(courses)
        form_progress = form_progress.filter(form__in=forms)
        topic_progress = topic_progress.filter(topic__in=topics)
        course_progress = course_progress.filter(course__in=courses)

    forms_deleted = form_progress.count()
    attempts_by_form = sorted(
        Counter(form_progress.values_list("form__slug", flat=True)).items()
    )
    form_progress.delete()

    topics_deleted = 0
    if include_topics:
        topics_deleted = topic_progress.count()
        topic_progress.delete()

    course_rows = course_progress.count()
    course_progress.update(
        completed_time=None,
        progress_percentage=0,
        last_accessed_content_type=None,
        last_accessed_object_id=None,
    )

    click.secho("\n--- Progress reset ---", fg="cyan", bold=True)
    click.secho(f"Site:    {site.name} ({site.domain}) [id {site.pk}]", fg="cyan")
    click.secho(f"Learner: {user.email}", fg="cyan", bold=True)
    click.secho(
        "Scope:   "
        + (
            ", ".join(course.slug for course in courses)
            if courses is not None
            else "ALL courses"
        ),
        fg="cyan",
    )
    click.secho(f"Deleted {forms_deleted} FormProgress row(s):", fg="green", bold=True)
    for slug, count in attempts_by_form:
        click.echo(f"  {slug}: {count}")
    click.secho(
        f"Deleted {topics_deleted} TopicProgress row(s)"
        + ("" if include_topics else " (--include-topics not set)"),
        fg="green",
    )
    click.secho(
        f"Reset {course_rows} CourseProgress row(s) to a freshly-registered state.",
        fg="green",
    )
