"""Seed a form sitting that happened OUTSIDE any course.

`FormProgressAdmin.in_course` (``freedom_ls/form_engine/admin.py``) documents
that the empty-value dash in its "In course" column means "sat standalone", not
"unknown": it reads the reverse one-to-one ``FormProgress.course_attempt`` and
returns ``None`` when there is no ``CourseFormAttempt``. Every FormProgress row
in the dev database was seeded through ``CourseFormAttemptFactory``, so every
one of them names a course and that branch had no browser fixture.

This command creates (idempotently) one ``FormProgress`` with **no**
``CourseFormAttempt`` pointing at it: a completed, scored sitting of an existing
form, hung off a dedicated QA user, with backdated ``start_time`` /
``completed_time`` so the changelist renders real timestamps.

Nothing about a standalone sitting is a special case in the data model --
``FormProgress`` FKs the user and the form directly, and the attempt-to-course
join lives in a separate ``learner_progress.CourseFormAttempt`` row -- so this
is simply the shape produced by not creating that join row. Completing it is
safe: ``recalculate_course_progress_on_form_attempt`` early-returns when there
is no course attempt, so no CourseProgress percentage anywhere is touched.

The login convention in this project is password == email address.

Usage:
    uv run python manage.py qa_create_standalone_form_sitting
    uv run python manage.py qa_create_standalone_form_sitting \
        --site-name DemoDev --email demodev@email.com --form-slug knowledge-check
"""

from datetime import timedelta
from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.form_engine.enums import FREE_TEXT_QUESTION_TYPES
from freedom_ls.form_engine.factories import FormProgressFactory, QuestionAnswerFactory
from freedom_ls.form_engine.models import (
    Form,
    FormProgress,
    FormQuestion,
    QuestionAnswer,
)
from freedom_ls.learner_progress.models import CourseFormAttempt

DEFAULT_SITE_NAME = "DemoDev"
DEFAULT_EMAIL = "qa-standalone-form@example.com"
DEFAULT_FORM_SLUG = "qa-form-first-form"

FREE_TEXT_ANSWER = "Answered outside any course, as a standalone sitting."

# Backdating keeps the row from sorting in among whatever the tester is doing
# right now, and gives the changelist two distinct, plausible timestamps.
STARTED_HOURS_AGO = 3
COMPLETED_HOURS_AGO = 2


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e


def _get_or_create_user(email: str, site: Site) -> tuple[User, bool]:
    """Return the sitting's user, creating a dedicated QA one if absent.

    An existing user is returned untouched -- this command is additive, and
    resetting the password of a user the tester is already logged in as would
    not be.
    """
    existing: User | None = User._base_manager.filter(email=email, site=site).first()
    if existing is not None:
        return existing, False

    user = cast(User, UserFactory(email=email, site=site))
    EmailAddress.objects.update_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )
    return user, True


def _get_form(form_slug: str, site: Site) -> Form:
    try:
        return Form._base_manager.get(slug=form_slug, site=site)
    except Form.DoesNotExist as e:
        raise click.ClickException(
            f"Form '{form_slug}' not found on site '{site.name}'."
        ) from e


def _existing_standalone(user: User, form: Form) -> FormProgress | None:
    """A sitting of `form` by `user` that no CourseFormAttempt points at."""
    return (
        FormProgress._base_manager.filter(
            user=user, form=form, course_attempt__isnull=True
        )
        .order_by("start_time")
        .first()
    )


def _answer(attempt: FormProgress, question: FormQuestion, site: Site) -> None:
    """Give `question` a real answer, correct where correctness is defined."""
    answer = cast(
        QuestionAnswer,
        QuestionAnswerFactory(form_progress=attempt, question=question, site=site),
    )
    if question.type in FREE_TEXT_QUESTION_TYPES:
        answer.text_answer = FREE_TEXT_ANSWER
        answer.save()
        return

    options = list(question.options.order_by("order"))
    correct = [option for option in options if option.correct]
    # A survey question has no correct option; pick the first so the sitting
    # still scores off real selections rather than an empty answer.
    answer.selected_options.set(correct or options[:1])


def _sit_standalone(user: User, form: Form, site: Site) -> FormProgress:
    """Create, answer, complete and backdate one course-less sitting."""
    attempt = cast(FormProgress, FormProgressFactory(user=user, form=form, site=site))

    questions = (
        FormQuestion._base_manager.filter(form_page__form=form)
        .prefetch_related("options")
        .order_by("form_page__order", "order")
    )
    for question in questions:
        _answer(attempt, question, site)

    # Score through complete(), so `scores` comes out in the shape the form's
    # own strategy really writes rather than a hand-rolled dict.
    attempt.complete()

    # start_time is auto_now_add and complete() stamps completed_time with
    # now(), so backdating has to happen after the save, via the queryset.
    now = timezone.now()
    FormProgress._base_manager.filter(pk=attempt.pk).update(
        start_time=now - timedelta(hours=STARTED_HOURS_AGO),
        completed_time=now - timedelta(hours=COMPLETED_HOURS_AGO),
    )
    attempt.refresh_from_db()
    return attempt


@click.command()
@click.option(
    "--site-name",
    default=DEFAULT_SITE_NAME,
    help=f"Site to create the sitting on (default: '{DEFAULT_SITE_NAME}').",
)
@click.option(
    "--email",
    default=DEFAULT_EMAIL,
    help=f"User who sat the form; created if absent (default: '{DEFAULT_EMAIL}').",
)
@click.option(
    "--form-slug",
    default=DEFAULT_FORM_SLUG,
    help=f"Slug of an existing form to sit (default: '{DEFAULT_FORM_SLUG}').",
)
def command(site_name: str, email: str, form_slug: str) -> None:
    """Seed one completed FormProgress that no CourseFormAttempt points at."""
    site = _get_site(site_name)
    user, user_created = _get_or_create_user(email, site)
    form = _get_form(form_slug, site)

    attempt = _existing_standalone(user, form)
    reused = attempt is not None
    if attempt is None:
        attempt = _sit_standalone(user, form, site)

    joins = CourseFormAttempt._base_manager.filter(form_progress_id=attempt.pk).count()
    answers = QuestionAnswer._base_manager.filter(form_progress=attempt).count()
    standalone_total = FormProgress._base_manager.filter(
        course_attempt__isnull=True
    ).count()

    click.secho("\n--- Standalone (course-less) form sitting ---", fg="cyan", bold=True)
    click.secho(f"Site:  {site.name} ({site.domain}) [id {site.pk}]", fg="cyan")
    click.secho(
        f"User:  {user.email} / {user.email}"
        f"{'  (created)' if user_created else '  (pre-existing, untouched)'}",
        fg="green",
        bold=True,
    )
    click.secho(f"Form:  {form.title}  [slug: {form.slug}]", fg="cyan")
    click.secho(
        f"FormProgress pk: {attempt.pk}"
        f"{'  (reused, already standalone)' if reused else '  (created)'}",
        fg="green",
        bold=True,
    )
    click.echo(f"  start_time     : {attempt.start_time}")
    click.echo(f"  completed_time : {attempt.completed_time}")
    click.echo(f"  scores         : {attempt.scores}")
    click.echo(f"  answers        : {answers}")
    click.secho(
        f"  CourseFormAttempt rows pointing at it: {joins}"
        f"{'  <- correct, renders the empty-value dash' if joins == 0 else '  <- WRONG'}",
        fg="green" if joins == 0 else "red",
        bold=True,
    )
    click.echo(f"Standalone FormProgress rows in the database: {standalone_total}")
    click.secho(
        "Admin: /admin/freedom_ls_form_engine/formprogress/"
        f"?q={user.email}  ('In course' column must show '-')",
        fg="green",
    )
