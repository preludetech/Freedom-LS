"""Seed a run of completed attempts at one form, so the start page's
"Previous attempts" list can be QA'd.

``view_form_start`` (``learner_interface/views.py``) hands the template
``completed_attempts(course_progress, collection_item)[:5]`` -- newest first,
sliced to five -- and ``partials/exam_previous_attempts.html`` renders one row
per attempt with ``completed_time|date:"j M Y"`` and, for a QUIZ, the stored
``scores`` as a percentage and a raw ``score / max_score`` pair.

Every other fixture command seeds at most one sitting per learner per form, so
neither the multi-row list nor the five-row cap had browser data. This command
builds N genuinely scored, genuinely completed sittings at an existing form:

* each attempt answers real questions, then goes through ``FormProgress.complete()``
  so its ``scores`` dict is the one the form's own strategy writes -- never a
  hand-written dict no real submission could produce;
* ``--scores`` gives the intended raw score of each attempt, oldest first. A
  score of N is produced by answering the first N questions correctly and the
  rest with a real wrong option, so the stored score is earned rather than
  stamped;
* ``completed_time`` is backdated one calendar day per attempt, ending today, so
  the rendered dates differ and the newest-first ordering is unambiguous.

By default the learner's existing attempts at the form are deleted first, so the
count is exactly ``len(--scores)`` -- an in-progress attempt left over from a
browser session would otherwise turn the start page into "Continue Form".

Usage:
    uv run python manage.py qa_create_form_attempt_history
    uv run python manage.py qa_create_form_attempt_history \
        --email demodev_quizqa@email.com \
        --course-slug qa-progression-block-course \
        --form-slug qa-progression-block-quiz \
        --scores 0,1,2,3,4,2
"""

import contextlib
from datetime import datetime, timedelta

import djclick as click

from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import ContentCollectionItem, Course
from freedom_ls.form_engine.models import (
    Form,
    FormProgress,
    FormQuestion,
    FormStrategy,
)
from freedom_ls.form_engine.queries import count_form_questions
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.learner_progress.queries import (
    completed_collection_item_ids,
    course_progress_for,
)
from freedom_ls.learner_progress.utils import calculate_course_progress_percentage
from freedom_ls.qa_helpers.management.commands.qa_complete_form import _course_placing
from freedom_ls.qa_helpers.management.commands.qa_create_report_cohort import (
    _complete_attempt,
    _quiz_questions,
)

DEFAULT_EMAIL = "demodev_quizqa@email.com"
DEFAULT_COURSE_SLUG = "qa-progression-block-course"
DEFAULT_FORM_SLUG = "qa-progression-block-quiz"
DEFAULT_SCORES = "0,1,2,3,4,2"

#: Attempts are stamped at midday rather than "now minus N days" so that no
#: attempt can straddle midnight and render on a neighbouring date.
STAMP_HOUR = 12

#: How long each sitting is made to have taken. Only start_time is affected;
#: it orders attempts that share a completed_time, which these never do.
SITTING_MINUTES = 20


def _parse_scores(raw: str, max_score: int) -> list[int]:
    """The requested raw score of each attempt, oldest first."""
    scores = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            score = int(chunk)
        except ValueError as error:
            raise click.ClickException(
                f"--scores must be a comma-separated list of integers; got '{chunk}'."
            ) from error
        if not 0 <= score <= max_score:
            raise click.ClickException(
                f"Score {score} is out of range for this form: it has "
                f"{max_score} question(s), so max_score is {max_score}."
            )
        scores.append(score)
    if not scores:
        raise click.ClickException("--scores named no attempts.")
    return scores


def _clear_existing(user: User, form: Form) -> None:
    """Delete this learner's attempts at this form, in-progress ones included.

    Guarded on the user as well as the form: a form is often sat by more than
    one fixture learner, and the caller asked about one of them. CourseFormAttempt
    and QuestionAnswer are both CASCADE off FormProgress, so the join row and the
    answers go with it.
    """
    existing = list(FormProgress.objects.filter(user=user, form=form))
    if not existing:
        click.secho(
            f"No existing FormProgress for {user.email} at '{form.slug}' to clear.",
            fg="yellow",
        )
        return

    click.secho(f"Deleting {len(existing)} existing attempt(s):", fg="yellow")
    for attempt in existing:
        state = (
            f"completed {attempt.completed_time:%Y-%m-%d %H:%M}"
            if attempt.completed_time
            else "IN PROGRESS"
        )
        click.secho(
            f"  FormProgress {attempt.pk} -- {state}, scores={attempt.scores}",
            fg="yellow",
        )
    deleted, by_model = FormProgress.objects.filter(user=user, form=form).delete()
    click.secho(f"  deleted {deleted} row(s): {by_model}", fg="yellow")


def _stamp_dates(count: int) -> list[datetime]:
    """One completed_time per attempt, oldest first, on consecutive days ending today."""
    today = timezone.now().replace(hour=STAMP_HOUR, minute=0, second=0, microsecond=0)
    return [today - timedelta(days=offset) for offset in reversed(range(count))]


def _wrong_orders(questions: list, score: int) -> set[int]:
    """Which question orders this attempt gets wrong to land on ``score``.

    The first ``score`` questions are answered correctly and the remainder
    wrongly, so an attempt's score is a property of its answers.
    """
    return {question.order for question in questions[score:]}


def _check_orders_are_distinct(questions: list[FormQuestion]) -> None:
    """`_complete_attempt` selects wrong answers by `question.order`.

    That is only a unique key while the form has one page: orders restart per
    page, so on a multi-page form two questions would share one order and be
    marked together. Refuse rather than seed a score nobody could earn.
    """
    orders = [question.order for question in questions]
    if len(set(orders)) != len(orders):
        raise click.ClickException(
            "This form's questions do not have distinct `order` values (a "
            "multi-page form), so a per-question right/wrong split cannot be "
            "addressed by order."
        )


@click.command()
@click.option("--site-name", default="DemoDev", help="Site the fixture lives on.")
@click.option("--email", default=DEFAULT_EMAIL, help="Learner sitting the form.")
@click.option(
    "--course-slug",
    default=DEFAULT_COURSE_SLUG,
    help="Course the form is placed in. Checked against the form's real placement.",
)
@click.option("--form-slug", default=DEFAULT_FORM_SLUG, help="Form to be sat.")
@click.option(
    "--scores",
    "raw_scores",
    default=DEFAULT_SCORES,
    help="Comma-separated raw scores, OLDEST first. One attempt per entry.",
)
@click.option(
    "--keep-existing",
    is_flag=True,
    default=False,
    help="Add to the learner's existing attempts instead of replacing them.",
)
def command(
    site_name: str,
    email: str,
    course_slug: str,
    form_slug: str,
    raw_scores: str,
    keep_existing: bool,
) -> None:
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as error:
        raise click.ClickException(f"Site '{site_name}' not found.") from error

    try:
        user = User.objects.get(email=email, site=site)
    except User.DoesNotExist as error:
        raise click.ClickException(
            f"User '{email}' not found on site '{site_name}'."
        ) from error

    try:
        form = Form.objects.get(slug=form_slug, site=site)
    except Form.DoesNotExist as error:
        raise click.ClickException(
            f"Form '{form_slug}' not found on site '{site_name}'."
        ) from error

    course, collection_item = _course_placing(form, site)
    if course.slug != course_slug:
        raise click.ClickException(
            f"Form '{form_slug}' is placed in '{course.slug}', not '{course_slug}'."
        )

    record = course_progress_for(user, course)
    if record is None:
        raise click.ClickException(
            f"{email} has no CourseProgress for '{course.slug}' -- register them first."
        )

    questions, options_by_question = _quiz_questions(form)
    max_score = count_form_questions(form)
    if len(questions) != max_score:
        raise click.ClickException(
            f"'{form_slug}' has {max_score} question(s) but only {len(questions)} "
            "carry options, so scores cannot be produced by answering."
        )
    _check_orders_are_distinct(questions)
    scores = _parse_scores(raw_scores, max_score)

    if not keep_existing:
        _clear_existing(user, form)

    stamps = _stamp_dates(len(scores))
    attempts: list[tuple[datetime, int, FormProgress]] = []
    for index, (score, completed_at) in enumerate(zip(scores, stamps, strict=True)):
        attempt = _complete_attempt(
            record=record,
            form=form,
            collection_item=collection_item,
            site=site,
            questions=questions,
            options_by_question=options_by_question,
            wrong_orders=_wrong_orders(questions, score),
            # learner_index only steers which distractor is picked; a fixed
            # even value keeps every wrong checkbox answer the same shape.
            learner_index=0,
            started_at=completed_at - timedelta(minutes=SITTING_MINUTES),
            completed_at=completed_at,
        )
        attempts.append((completed_at, score, attempt))
        earned = (attempt.scores or {}).get("score")
        if earned != score:
            raise click.ClickException(
                f"Attempt {index + 1} scored {earned}, not the requested {score}."
            )

    _report(site, user, course, form, collection_item, record, attempts)


def _report(
    site: Site,
    user: User,
    course: Course,
    form: Form,
    collection_item: ContentCollectionItem,
    record: CourseProgress,
    attempts: list[tuple[datetime, int, FormProgress]],
) -> None:
    """Print the seeded run newest first, the way the start page lists it."""
    items = list(course.viewable_collection_items())
    index = items.index(collection_item) + 1 if collection_item in items else None

    click.secho("\n--- Form attempt history ---", fg="cyan", bold=True)
    click.secho(f"Site:    {site.name} ({site.domain}) [id {site.pk}]", fg="cyan")
    click.secho(f"Learner: {user.email}", fg="cyan")
    click.secho(f"Course:  {course.title} ({course.slug})", fg="cyan")
    click.secho(
        f"Form:    {form.title} ({form.slug}) -- {form.strategy}, "
        f"pass {form.quiz_pass_percentage}%",
        fg="cyan",
    )
    if index is not None:
        click.secho(f"URL:     /courses/{course.slug}/{index}/", fg="cyan")

    click.secho(
        f"\n{len(attempts)} completed attempt(s), newest first "
        "(the start page lists the first five):",
        fg="green",
        bold=True,
    )
    for position, (completed_at, _requested, attempt) in enumerate(
        sorted(attempts, key=lambda entry: entry[0], reverse=True), start=1
    ):
        stored = attempt.scores or {}
        percentage: int | None = None
        if form.strategy == FormStrategy.QUIZ:
            # A zero-question form has max_score 0, which quiz_percentage()
            # raises on rather than dividing by zero.
            with contextlib.suppress(ValueError):
                percentage = attempt.quiz_percentage()
        listed = "listed" if position <= 5 else "SLICED OFF"
        click.secho(
            f"  {position}. {completed_at:%-d %b %Y}  "
            f"{stored.get('score')}/{stored.get('max_score')}"
            + (f" ({percentage}%)" if percentage is not None else "")
            + f"  [{listed}]  {attempt.pk}",
            fg="green" if position <= 5 else "yellow",
        )

    # complete() fires form_attempt_completed, which recalculates this record,
    # so the in-memory copy is stale by now.
    record.refresh_from_db()
    percentage = calculate_course_progress_percentage(
        record.course, completed_collection_item_ids(record)
    )
    stored_percentage = record.progress_percentage
    click.secho(
        f"\nCourseProgress {record.pk}: stored {stored_percentage}%, "
        f"truthful {percentage}%",
        fg="cyan" if percentage == stored_percentage else "yellow",
    )
