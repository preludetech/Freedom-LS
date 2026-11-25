"""Seed the browser-QA walkthrough for retiring removed content, BEFORE the
tester retires anything: learners whose records will point at content that a
later content save retires.

Needs the demo content loaded (the "Functionality Demo" courses). Creates
(idempotently) on one site (default: DemoDev):

1. Learners ``qa-retire-a@example.com`` and ``qa-retire-b@example.com``
   (password equals the email), each individually registered on
   "Functionality Demo - shuffled quiz" with its first item, the topic
   "Planets and the sky", complete. So the "Shuffled quiz" at index 2 is open
   to them, and neither has sat it.
2. Cohort "QA Retire Cohort" in organisation ``demodev``, registered on
   "Functionality Demo - Course Parts" and "Functionality Demo - shuffled quiz",
   with members ``qa-cohort-1@example.com`` and ``qa-cohort-2@example.com``
   (password equals the email).
3. Course Parts progress: both members have completed "Welcome" and "What to
   Expect"; cohort-2 has also completed "Key Ideas", "Going Deeper" and
   "Summary" (every live topic, neither form).
4. One completed, scored sitting each of the "Shuffled quiz", sat through the
   app's own ``complete()`` (served paper, ``asked``, scores, progress
   recalculation). cohort-1 answers "What does the Moon orbit?" with "The Sun"
   and "What colour is the sky at midday?" with "Green" (both wrong) and every
   other question correctly; cohort-2 answers everything correctly. If some of
   the quiz is already retired when this runs, the sitting is sat as it would
   have been before the retirement (see ``qa_create_retired_content_scenario``).

A re-run creates nothing twice and leaves completed sittings alone.

Usage:
    uv run python manage.py qa_create_retire_walkthrough_scenario
    uv run python manage.py qa_create_retire_walkthrough_scenario --site-name DemoDev
"""

import djclick as click

from django.contrib.sites.models import Site

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.form_engine.models import Form, FormProgress
from freedom_ls.learner_management.models import Cohort
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.qa_helpers.management.commands.qa_create_multiselect_quiz_scoring import (
    _add_member,
    _get_or_create_user,
    _get_site,
    _record_for,
    _register,
    _register_cohort,
)
from freedom_ls.qa_helpers.management.commands.qa_create_retired_content_scenario import (
    ORGANISATION_SLUG,
    PARTS_COURSE_SLUG,
    QUIZ_COURSE_SLUG,
    QUIZ_TITLE,
    LearnerSpec,
    _complete_course_parts,
    _complete_topic,
    _course,
    _get_or_create_cohort,
    _sit_quiz_before_retirement,
    _topic_placement,
)

QUIZ_FIRST_TOPIC = "Planets and the sky"

# Individually registered learners who have not sat the quiz yet.
FRESH_LEARNERS: list[tuple[str, str]] = [
    ("A", "qa-retire-a@example.com"),
    ("B", "qa-retire-b@example.com"),
]

COHORT_LEARNERS = [
    LearnerSpec(
        label="1",
        email="qa-cohort-1@example.com",
        topics=("Welcome", "What to Expect"),
        extra_topics=(),
        quiz_overrides={
            "What does the Moon orbit?": ("The Sun",),
            "What colour is the sky at midday?": ("Green",),
        },
    ),
    LearnerSpec(
        label="2",
        email="qa-cohort-2@example.com",
        topics=("Welcome", "What to Expect", "Key Ideas", "Going Deeper", "Summary"),
        extra_topics=(),
        quiz_overrides={},
    ),
]


def _shuffled_quiz(course: Course) -> Form:
    for item in course.viewable_collection_items():
        if isinstance(item.child, Form) and item.child.title == QUIZ_TITLE:
            return item.child
    raise click.ClickException(f"No form '{QUIZ_TITLE}' in '{course.slug}'.")


def _seed_fresh_learner(
    label: str, email: str, quiz_course: Course, quiz: Form, site: Site
) -> User:
    user, _created = _get_or_create_user(site, email, "Retire", label)
    _register(user, quiz_course, site)
    record = _record_for(user, quiz_course)
    _complete_topic(record, _topic_placement(quiz_course, QUIZ_FIRST_TOPIC))
    if FormProgress.objects.filter(user=user, form=quiz).exists():
        click.secho(
            f"{email} already has a sitting of '{quiz.title}'; clear it with "
            "qa_clear_form_sittings before testing a first sitting.",
            fg="yellow",
        )
    return user


def _seed_cohort_learner(
    spec: LearnerSpec,
    cohort: Cohort,
    parts_course: Course,
    quiz_course: Course,
    quiz: Form,
    site: Site,
) -> tuple[User, FormProgress]:
    user, _created = _get_or_create_user(site, spec.email, "Cohort", spec.label)
    _add_member(user, cohort, site)
    _complete_course_parts(spec, user, parts_course, site)
    sitting = _sit_quiz_before_retirement(
        user, quiz_course, quiz, spec.quiz_overrides, site
    )
    return user, sitting


def _print_records(user: User) -> None:
    for record in CourseProgress._base_manager.filter(
        learner__user=user
    ).select_related("course"):
        click.echo(
            f"  CourseProgress {record.pk}  '{record.course.title}'  "
            f"{record.progress_percentage}%"
        )


@click.command()
@click.option(
    "--site-name",
    default="DemoDev",
    help="Site name to create the data on (default: 'DemoDev').",
)
def command(site_name: str) -> None:
    """Seed learners for the retire-removed-content browser walkthrough."""
    site = _get_site(site_name)
    parts_course = _course(PARTS_COURSE_SLUG, site)
    quiz_course = _course(QUIZ_COURSE_SLUG, site)
    quiz = _shuffled_quiz(quiz_course)

    fresh = [
        _seed_fresh_learner(label, email, quiz_course, quiz, site)
        for label, email in FRESH_LEARNERS
    ]

    cohort = _get_or_create_cohort(site)
    for course in (parts_course, quiz_course):
        _register_cohort(cohort, course, site)
    seated = [
        _seed_cohort_learner(spec, cohort, parts_course, quiz_course, quiz, site)
        for spec in COHORT_LEARNERS
    ]

    click.secho("\n--- Retire walkthrough QA data ---", fg="cyan", bold=True)
    click.secho(f"Site: {site.name} ({site.domain}) [id {site.pk}]", fg="cyan")
    for user in fresh:
        click.secho(f"\n{user.email} / {user.email}  user pk={user.pk}", fg="green")
        _print_records(user)
    click.secho(
        f"\nCohort: '{cohort.name}'  pk={cohort.pk}  "
        f"/educator/organisations/{ORGANISATION_SLUG}/cohorts/{cohort.pk}",
        fg="cyan",
    )
    for user, sitting in seated:
        click.secho(f"\n{user.email} / {user.email}  user pk={user.pk}", fg="green")
        _print_records(user)
        click.echo(
            f"  Quiz sitting FormProgress pk={sitting.pk}  "
            f"completed={sitting.completed_time}  scores={sitting.scores}  "
            f"answers={sitting.answers.count()}  "
            f"served_paper={'yes' if sitting.served_paper else 'no'}"
        )
