"""Seed browser-QA data for the multi-select (checkboxes) quiz scoring fix.

Creates, idempotently, on the requested site:

1. A dedicated login-ready learner (``demodev_quizqa@email.com``, password ==
   email, verified + primary allauth EmailAddress) so QA does not have to use
   the ``demodev@email.com`` superuser.
2. Registration for the "all question types" course built by
   ``qa_create_form_question_types`` (whose QUIZ form has
   ``quiz_pass_percentage=50``, ``quiz_show_incorrect=True`` and a
   ``checkboxes`` question with 3 options / 2 correct). The helpers from that
   command are reused so the course/form are created here if missing.
3. A second single-item course whose only viewable item is a QUIZ form with
   ``quiz_pass_percentage`` left as NULL (results page must render a score with
   no pass/fail verdict). It holds a ``checkboxes`` question (3 options, 2
   correct) plus a single-select ``multiple_choice`` question so the score is
   non-trivial.

4. A cohort registered for BOTH courses, containing the QA learner plus two
   extra learners that already have genuinely scored, completed quiz attempts
   (one above and one below the 50% pass mark, plus attempts on the
   NULL-pass-mark quiz). This gives the educator cohort-course-progress panel
   real quiz percentages to render, including the "score but no verdict" case.
   An educator with the guardian ``view_cohort`` permission is created too.

Both forms sit at item index 1 of their own course, so neither is blocked by
the player's sequential item unlocking. The main QA learner is deliberately
left with NO progress so the player can be walked from a clean state.

Usage:
    uv run python manage.py qa_create_multiselect_quiz_scoring
    uv run python manage.py qa_create_multiselect_quiz_scoring --site-name DemoDev
"""

from typing import cast

import djclick as click
from allauth.account.models import EmailAddress
from guardian.shortcuts import assign_perm

from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    CourseFactory,
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.content_engine.models import (
    Course,
    Form,
    FormPage,
    FormQuestion,
    FormStrategy,
    QuestionType,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    UserCourseRegistrationFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    UserCourseRegistration,
)
from freedom_ls.learner_progress.factories import (
    CourseProgressFactory,
    FormProgressFactory,
    QuestionAnswerFactory,
)
from freedom_ls.learner_progress.models import (
    CourseProgress,
    FormProgress,
    QuestionAnswer,
)
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.qa_helpers.management.commands.qa_create_form_question_types import (
    _attach_form_to_course,
    _build_form,
    _get_or_create_course,
)

LEARNER_EMAIL = "demodev_quizqa@email.com"

NO_PCT_COURSE_TITLE = "QA Quiz Without Pass Percentage"
NO_PCT_COURSE_SLUG = "qa-quiz-no-pass-pct-course"

NO_PCT_FORM_TITLE = "QA Quiz Without Pass Percentage Form"
NO_PCT_FORM_SLUG = "qa-quiz-no-pass-pct-form"

NO_PCT_PAGE_TITLE = "QA No Pass Percentage Page"
NO_PCT_PAGE_SLUG = "qa-no-pass-pct-page"

NO_PCT_CHECKBOX_QUESTION = "Which two of these are correct? (no pass mark set)"
NO_PCT_MC_QUESTION = "Pick the one correct answer (no pass mark set)"

NO_PCT_CHECKBOX_OPTIONS: list[tuple[str, bool]] = [
    ("No-pct checkbox option A", True),
    ("No-pct checkbox option B", True),
    ("No-pct checkbox option C", False),
]
COHORT_NAME = "QA Multi-Select Quiz Scoring Cohort"
EDUCATOR_EMAIL = "demodev_quizqa_educator@email.com"

# (email, first name, last name, answer every option-question correctly?)
COHORT_LEARNERS: list[tuple[str, str, str, bool]] = [
    ("demodev_quizqa_pass@email.com", "Priya", "Passer", True),
    ("demodev_quizqa_fail@email.com", "Fred", "Failer", False),
]

NO_PCT_MC_OPTIONS: list[tuple[str, bool]] = [
    ("No-pct MC option A", True),
    ("No-pct MC option B", False),
    ("No-pct MC option C", False),
]


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e


def _get_or_create_user(
    site: Site, email: str, first_name: str, last_name: str
) -> tuple[User, bool]:
    """Create a login-ready QA user (password == email), or reuse an existing one."""
    existing: User | None = User.objects.filter(email=email).first()
    if existing is not None:
        existing.is_active = True
        existing.set_password(email)
        existing.save(update_fields=["is_active", "password"])
        user = existing
        created = False
    else:
        user = cast(
            User,
            UserFactory(
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
                password=email,
                site=site,
            ),
        )
        created = True

    EmailAddress.objects.update_or_create(
        user=user,
        email=user.email,
        defaults={"verified": True, "primary": True},
    )
    return user, created


def _get_or_create_no_pct_course(site: Site) -> Course:
    existing: Course | None = Course.objects.filter(
        slug=NO_PCT_COURSE_SLUG, site=site
    ).first()
    if existing is not None:
        return existing
    return cast(
        Course,
        CourseFactory(
            title=NO_PCT_COURSE_TITLE,
            slug=NO_PCT_COURSE_SLUG,
            description=(
                "Dedicated course for QA of quiz results when no pass "
                "percentage is configured."
            ),
            site=site,
        ),
    )


def _add_options(
    question: FormQuestion, options: list[tuple[str, bool]], site: Site
) -> None:
    for i, (text, correct) in enumerate(options):
        QuestionOptionFactory(
            question=question,
            text=text,
            value=str(i + 1),
            order=i,
            correct=correct,
            site=site,
        )


def _build_no_pct_form(site: Site) -> Form:
    """QUIZ form with quiz_pass_percentage left NULL. Idempotent."""
    existing: Form | None = Form.objects.filter(
        slug=NO_PCT_FORM_SLUG, site=site
    ).first()
    if existing is not None:
        return existing

    form = cast(
        Form,
        FormFactory(
            title=NO_PCT_FORM_TITLE,
            slug=NO_PCT_FORM_SLUG,
            strategy=FormStrategy.QUIZ,
            quiz_show_incorrect=True,
            quiz_pass_percentage=None,
            site=site,
        ),
    )

    page = cast(
        FormPage,
        FormPageFactory(
            form=form,
            title=NO_PCT_PAGE_TITLE,
            slug=NO_PCT_PAGE_SLUG,
            order=0,
            site=site,
        ),
    )

    checkbox_question = cast(
        FormQuestion,
        FormQuestionFactory(
            form_page=page,
            question=NO_PCT_CHECKBOX_QUESTION,
            type=QuestionType.CHECKBOXES,
            required=True,
            order=0,
            site=site,
        ),
    )
    _add_options(checkbox_question, NO_PCT_CHECKBOX_OPTIONS, site)

    mc_question = cast(
        FormQuestion,
        FormQuestionFactory(
            form_page=page,
            question=NO_PCT_MC_QUESTION,
            type=QuestionType.MULTIPLE_CHOICE,
            required=True,
            order=1,
            site=site,
        ),
    )
    _add_options(mc_question, NO_PCT_MC_OPTIONS, site)

    return form


def _register(learner: User, course: Course, site: Site) -> None:
    if not UserCourseRegistration.objects.filter(
        user=learner, collection=course, site=site
    ).exists():
        UserCourseRegistrationFactory(
            user=learner,
            collection=course,
            site=site,
            organisation=get_default_organisation(site),
        )


def _ensure_course_progress_row(user: User, course: Course, site: Site) -> None:
    """Pre-create CourseProgress WITH a site.

    ``FormProgress.complete()`` triggers ``update_course_progress_on_completion``
    which creates a ``CourseProgress`` without a ``site``, violating the NOT NULL
    constraint. Creating the row up front avoids that.
    """
    if not CourseProgress.objects.filter(user=user, course=course, site=site).exists():
        CourseProgressFactory(user=user, course=course, site=site)


def _complete_quiz_attempt(
    user: User, form: Form, site: Site, *, answer_correctly: bool
) -> FormProgress:
    """Create a genuinely scored, completed quiz attempt. Idempotent.

    Answers every option-backed question on the form: either every option marked
    ``correct=True`` (a correct answer), or the first option marked
    ``correct=False`` (an incorrect answer). Free-text questions are left
    unanswered - they have no correct option so they always score zero.
    """
    existing: FormProgress | None = FormProgress.objects.filter(
        user=user, form=form, site=site
    ).first()
    if existing is not None and existing.completed_time is not None:
        return existing

    attempt = existing or cast(
        FormProgress, FormProgressFactory(user=user, form=form, site=site)
    )

    for question in FormQuestion.objects.filter(form_page__form=form).order_by("order"):
        options = list(question.options.order_by("order"))
        if not options:
            continue
        if answer_correctly:
            chosen = [o for o in options if o.correct is True]
        else:
            chosen = [o for o in options if o.correct is False][:1]
        if not chosen:
            continue
        answer: QuestionAnswer | None = QuestionAnswer.objects.filter(
            form_progress=attempt, question=question
        ).first()
        if answer is None:
            answer = cast(
                QuestionAnswer,
                QuestionAnswerFactory(
                    form_progress=attempt, question=question, site=site
                ),
            )
        answer.selected_options.set(chosen)

    attempt.complete()
    attempt.refresh_from_db()
    return attempt


def _get_or_create_cohort(site: Site) -> Cohort:
    existing: Cohort | None = Cohort.objects.filter(name=COHORT_NAME, site=site).first()
    if existing is not None:
        return existing
    return cast(
        Cohort,
        CohortFactory(
            name=COHORT_NAME, site=site, organisation=get_default_organisation(site)
        ),
    )


def _register_cohort(cohort: Cohort, course: Course, site: Site) -> None:
    if not CohortCourseRegistration.objects.filter(
        cohort=cohort, collection=course, site=site
    ).exists():
        CohortCourseRegistrationFactory(cohort=cohort, collection=course, site=site)


def _add_member(user: User, cohort: Cohort, site: Site) -> None:
    if not CohortMembership.objects.filter(
        user=user, cohort=cohort, site=site
    ).exists():
        CohortMembershipFactory(user=user, cohort=cohort, site=site)


def _item_index(course: Course, form: Form) -> int:
    for i, item in enumerate(course.viewable_items()):
        if item.pk == form.pk and isinstance(item, Form):
            return i + 1
    raise click.ClickException(
        f"Form '{form.slug}' is not a viewable item of course '{course.slug}'."
    )


@click.command()
@click.option(
    "--site-name",
    default="DemoDev",
    help="Site name to create the data on (default: 'DemoDev').",
)
def command(site_name: str) -> None:
    """Seed the checkbox-quiz scoring browser-QA fixtures and their learner."""
    site = _get_site(site_name)
    learner, created = _get_or_create_user(site, LEARNER_EMAIL, "Quiz", "Scoring QA")

    # Course 1: the existing all-question-types QUIZ (pass percentage 50).
    types_course = _get_or_create_course(site)
    types_form = _build_form(site)
    _attach_form_to_course(types_course, types_form, site)
    _register(learner, types_course, site)
    types_index = _item_index(types_course, types_form)

    # Course 2: QUIZ with no pass percentage.
    no_pct_course = _get_or_create_no_pct_course(site)
    no_pct_form = _build_no_pct_form(site)
    _attach_form_to_course(no_pct_course, no_pct_form, site)
    _register(learner, no_pct_course, site)
    no_pct_index = _item_index(no_pct_course, no_pct_form)

    # Cohort for the educator cohort-course-progress panel, registered for BOTH
    # courses so one panel exercises the pass-mark and the no-pass-mark quiz.
    cohort = _get_or_create_cohort(site)
    for course in (types_course, no_pct_course):
        _register_cohort(cohort, course, site)
    _add_member(learner, cohort, site)

    educator, educator_created = _get_or_create_user(
        site, EDUCATOR_EMAIL, "Quinn", "QuizQA Educator"
    )
    assign_perm("view_cohort", educator, cohort)

    attempts: list[tuple[User, Form, FormProgress]] = []
    for email, first_name, last_name, answer_correctly in COHORT_LEARNERS:
        learner, _ = _get_or_create_user(site, email, first_name, last_name)
        _add_member(learner, cohort, site)
        for course, form in ((types_course, types_form), (no_pct_course, no_pct_form)):
            _register(learner, course, site)
            _ensure_course_progress_row(learner, course, site)
            attempt = _complete_quiz_attempt(
                learner, form, site, answer_correctly=answer_correctly
            )
            attempts.append((learner, form, attempt))

    click.secho("\n--- Multi-select quiz scoring QA data ---", fg="cyan", bold=True)
    click.secho(f"Site:  {site.name} ({site.domain}) [id {site.pk}]", fg="cyan")
    click.secho(
        f"{'Created' if created else 'Reused'} learner login: "
        f"{learner.email} / {learner.email}",
        fg="green",
        bold=True,
    )

    click.secho(
        f"\n[1] {types_course.title}  [slug: {types_course.slug}]", fg="cyan", bold=True
    )
    click.echo(f"    Form slug           : {types_form.slug}")
    click.echo(f"    quiz_pass_percentage: {types_form.quiz_pass_percentage}")
    click.echo(f"    quiz_show_incorrect : {types_form.quiz_show_incorrect}")
    click.secho(
        f"    Start screen        : /courses/{types_course.slug}/{types_index}/",
        fg="green",
    )
    click.secho(
        f"    Runner page 1       : "
        f"/courses/{types_course.slug}/{types_index}/fill_form/1",
        fg="green",
    )

    click.secho(
        f"\n[2] {no_pct_course.title}  [slug: {no_pct_course.slug}]",
        fg="cyan",
        bold=True,
    )
    click.echo(f"    Form slug           : {no_pct_form.slug}")
    click.echo(f"    quiz_pass_percentage: {no_pct_form.quiz_pass_percentage}")
    click.echo(f"    quiz_show_incorrect : {no_pct_form.quiz_show_incorrect}")
    click.secho(
        f"    Start screen        : /courses/{no_pct_course.slug}/{no_pct_index}/",
        fg="green",
    )
    click.secho(
        f"    Runner page 1       : "
        f"/courses/{no_pct_course.slug}/{no_pct_index}/fill_form/1",
        fg="green",
    )

    click.secho("\nCheckboxes questions (3 options, 2 correct):", fg="cyan", bold=True)
    for form in (types_form, no_pct_form):
        for question in FormQuestion.objects.filter(
            form_page__form=form, type=QuestionType.CHECKBOXES
        ).order_by("order"):
            click.echo(f"  {form.slug} :: {question.question}")
            for option in question.options.order_by("order"):
                mark = "CORRECT" if option.correct else "incorrect"
                click.echo(f"    - {option.text}  [{mark}]")

    click.secho("\n--- Educator cohort panel ---", fg="cyan", bold=True)
    click.secho(f"Cohort: {cohort.name}", fg="cyan")
    click.secho(
        f"  /educator/organisations/{cohort.organisation.slug}/cohorts/{cohort.pk}",
        fg="green",
        bold=True,
    )
    click.secho(
        f"  /educator/organisations/{cohort.organisation.slug}"
        f"/cohorts/{cohort.pk}/__tabs/course_progress",
        fg="green",
    )
    click.secho(
        f"{'Created' if educator_created else 'Reused'} educator login: "
        f"{educator.email} / {educator.email} (guardian view_cohort granted)",
        fg="green",
        bold=True,
    )
    click.echo(
        "  Registered courses: "
        + ", ".join(
            sorted(
                CohortCourseRegistration.objects.filter(
                    cohort=cohort, site=site
                ).values_list("collection__slug", flat=True)
            )
        )
    )
    click.echo(
        f"  Members: {CohortMembership.objects.filter(cohort=cohort, site=site).count()}"
    )
    click.secho("Completed quiz attempts:", fg="cyan")
    for learner, form, attempt in attempts:
        pass_mark = form.quiz_pass_percentage
        verdict = (
            "no verdict (pass mark unset)"
            if pass_mark is None
            else ("PASS" if attempt.passed() else "FAIL")
        )
        click.echo(
            f"  {learner.email} :: {form.slug} :: "
            f"{attempt.scores} = {attempt.quiz_percentage()}% "
            f"(pass mark {pass_mark}) -> {verdict}"
        )
