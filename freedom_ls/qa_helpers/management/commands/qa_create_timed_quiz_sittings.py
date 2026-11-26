"""Seed a cohort learner with one time-expired and one learner-submitted sitting
at a timed quiz, so the cohort report's attempts table shows both completion
reasons side by side.

The cohort is registered on the course through ``register_cohort_for_course``,
whose post_save fan-out mints a ``CourseProgress`` for every member, exactly as
the educator interface does. Each sitting is opened with
``get_or_create_incomplete`` -- the call ``start_attempt`` makes -- so the
``FormProgress`` and its ``CourseFormAttempt`` are written together. Its
``start_time`` is then backdated and the sitting finished through
``FormProgress.complete()``, so the score, ``completion_reason``,
``time_limit_minutes`` and ``completed_time`` are the ones the application
itself writes:

* the expired sitting starts well over the limit ago and is completed with
  ``CompletionReason.TIME_EXPIRED``, so ``completed_time`` is clamped to
  ``start_time + time_limit_minutes``;
* the submitted sitting starts a few minutes ago and is completed with the
  default reason, so ``completed_time`` is now.

The learner's existing sittings at the form are deleted first, so a rerun
leaves exactly these two.

The login convention in this project is password == email address.

Usage:
    uv run python manage.py qa_create_timed_quiz_sittings
    uv run python manage.py qa_create_timed_quiz_sittings \
        --cohort-name "Cohort 2025.03.04" --email demodev_s1@email.com
"""

from datetime import timedelta
from typing import cast

import djclick as click

from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import ContentCollectionItem, Course
from freedom_ls.form_engine.enums import CompletionReason
from freedom_ls.form_engine.factories import QuestionAnswerFactory
from freedom_ls.form_engine.models import (
    Form,
    FormProgress,
    FormQuestion,
    QuestionAnswer,
    QuestionOption,
)
from freedom_ls.learner_management.models import Cohort, CohortMembership
from freedom_ls.learner_management.utils import register_cohort_for_course
from freedom_ls.learner_progress.attempts import get_or_create_incomplete
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.learner_progress.queries import course_progress_for
from freedom_ls.qa_helpers.management.commands.qa_complete_form import _course_placing
from freedom_ls.qa_helpers.management.commands.qa_create_report_cohort import (
    _choose_options,
    _quiz_questions,
)

DEFAULT_COURSE_SLUG = "functionality-demo-timed-quiz"
DEFAULT_COHORT_NAME = "Cohort 2025.03.04"
DEFAULT_EMAIL = "demodev_s1@email.com"

#: How long ago the expired sitting began, in minutes past its limit.
EXPIRED_OVERRUN_MINUTES = 30
#: How long the submitted sitting took.
SUBMITTED_AFTER_MINUTES = 4


def _timed_form(course: Course, site: Site) -> tuple[Form, ContentCollectionItem]:
    """The course's one timed form and its placement."""
    for item in ContentCollectionItem.objects.filter(
        collection_id=course.pk, site=site
    ).order_by("order"):
        child = item.child
        if isinstance(child, Form) and child.time_limit_minutes:
            course_found, placement = _course_placing(child, site)
            if course_found.pk == course.pk:
                return child, placement
    raise click.ClickException(f"'{course.slug}' places no timed form.")


def _clear_existing(user: User, form: Form) -> None:
    """Delete this learner's sittings at this form. CourseFormAttempt and
    QuestionAnswer CASCADE off FormProgress, so they go with it."""
    existing = FormProgress.objects.filter(user=user, form=form)
    for sitting in existing:
        click.secho(
            f"  removing FormProgress {sitting.pk} "
            f"(completed {sitting.completed_time}, {sitting.completion_reason})",
            fg="yellow",
        )
    deleted, by_model = existing.delete()
    click.secho(f"  deleted {deleted} row(s): {by_model}", fg="yellow")


def _answer(
    sitting: FormProgress,
    questions: list[FormQuestion],
    options_by_question: dict[str, list[QuestionOption]],
    wrong_orders: set[int],
    site: Site,
) -> None:
    for question in questions:
        options = options_by_question[str(question.id)]
        chosen = _choose_options(
            question, options, question.order in wrong_orders, learner_index=0
        )
        if not chosen:
            continue
        answer = cast(
            QuestionAnswer,
            QuestionAnswerFactory(form_progress=sitting, question=question, site=site),
        )
        answer.selected_options.set(chosen)


def _sit(
    record: CourseProgress,
    collection_item: ContentCollectionItem,
    started_minutes_ago: int,
    reason: CompletionReason,
    questions: list[FormQuestion],
    options_by_question: dict[str, list[QuestionOption]],
    wrong_orders: set[int],
    site: Site,
) -> FormProgress:
    """Open a sitting the way start_attempt does, backdate it, answer, complete."""
    sitting = get_or_create_incomplete(record, collection_item)
    # start_time is auto_now_add, so it is backdated through the queryset.
    FormProgress.objects.filter(pk=sitting.pk).update(
        start_time=timezone.now() - timedelta(minutes=started_minutes_ago)
    )
    sitting.refresh_from_db()
    _answer(sitting, questions, options_by_question, wrong_orders, site)
    sitting.complete(reason)
    sitting.refresh_from_db()
    if sitting.completion_reason != reason:
        raise click.ClickException(
            f"FormProgress {sitting.pk} completed as {sitting.completion_reason}, "
            f"not {reason}."
        )
    return sitting


@click.command()
@click.option("--site-name", default="DemoDev", help="Site the fixture lives on.")
@click.option("--course-slug", default=DEFAULT_COURSE_SLUG, help="Timed-quiz course.")
@click.option("--cohort-name", default=DEFAULT_COHORT_NAME, help="Cohort to register.")
@click.option("--email", default=DEFAULT_EMAIL, help="Cohort member who sits the quiz.")
def command(site_name: str, course_slug: str, cohort_name: str, email: str) -> None:
    try:
        site = Site.objects.get(name=site_name)
        course = Course.objects.get(site=site, slug=course_slug)
        cohort = Cohort.objects.get(site=site, name=cohort_name)
        user = User.objects.get(site=site, email=email)
    except (
        Site.DoesNotExist,
        Course.DoesNotExist,
        Cohort.DoesNotExist,
        User.DoesNotExist,
    ) as error:
        raise click.ClickException(str(error)) from error

    if not CohortMembership.objects.filter(
        cohort=cohort, learner__user=user, site=site
    ).exists():
        raise click.ClickException(f"{email} is not a member of '{cohort.name}'.")

    registered = register_cohort_for_course(
        cohort, course, reason="QA: timed quiz sittings"
    )
    click.secho(
        f"Cohort '{cohort.name}' "
        + ("registered on" if registered else "already registered on")
        + f" '{course.title}'.",
        fg="green",
    )

    record = course_progress_for(user, course)
    if record is None:
        raise click.ClickException(
            f"{email} has no CourseProgress for '{course_slug}'."
        )

    form, collection_item = _timed_form(course, site)
    limit = cast(int, form.time_limit_minutes)
    questions, options_by_question = _quiz_questions(form)
    orders = sorted({question.order for question in questions})

    _clear_existing(user, form)
    expired = _sit(
        record,
        collection_item,
        limit + EXPIRED_OVERRUN_MINUTES,
        CompletionReason.TIME_EXPIRED,
        questions,
        options_by_question,
        # Ran out of time half-way: the back half is answered wrongly.
        set(orders[len(orders) // 2 :]),
        site,
    )
    submitted = _sit(
        record,
        collection_item,
        SUBMITTED_AFTER_MINUTES,
        CompletionReason.LEARNER_SUBMITTED,
        questions,
        options_by_question,
        set(),
        site,
    )

    record.refresh_from_db()
    click.secho("\n--- Timed quiz sittings ---", fg="cyan", bold=True)
    click.secho(f"Site:    {site.name} ({site.domain})", fg="cyan")
    click.secho(f"Cohort:  {cohort.name} [{cohort.pk}]", fg="cyan")
    click.secho(f"Learner: {user.email} [{user.pk}] (password = email)", fg="cyan")
    click.secho(f"Course:  {course.title} ({course.slug})", fg="cyan")
    click.secho(f"Form:    {form.title} ({form.slug}), {limit} min limit", fg="cyan")
    click.secho(f"CourseProgress {record.pk}: {record.progress_percentage}%", fg="cyan")
    for sitting in (expired, submitted):
        click.secho(
            f"  FormProgress {sitting.pk}: {sitting.completion_reason}, "
            f"limit {sitting.time_limit_minutes}, "
            f"{sitting.start_time:%H:%M:%S} -> {sitting.completed_time:%H:%M:%S}, "
            f"scores={sitting.scores}",
            fg="green",
        )
