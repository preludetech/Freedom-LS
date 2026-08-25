"""Seed a CLEAN scored quiz for the checkbox-scoring learner walkthrough.

``qa_create_form_question_types`` builds a QUIZ containing ``short_text`` and
``long_text`` questions. ``score_quiz()`` counts every question toward
``max_score`` and free-text can never be scored correct, so that form's ceiling
is 2/4 = 50% - which makes every expected percentage in the checkbox-scoring
walkthrough awkward to read.

This command builds (idempotently) a single-item course whose only viewable
item is a QUIZ form made of **option-backed questions only**, so 100% is
reachable:

1. ``multiple_choice`` - 3 options, exactly 1 correct, **required**.
2. ``checkboxes``      - 3 options, exactly 2 correct, **NOT required**.

The checkboxes question is deliberately optional: a required question with no
ticked option is rejected with a 422 by the runner, so the "tick nothing" case
of the scoring matrix could not be submitted at all if it were required.

Arithmetic, with the multiple-choice question answered correctly (max_score 2):

* checkboxes exactly right -> 2/2 = 100% >= 80 -> PASS
* checkboxes anything else -> 1/2 =  50% <  80 -> FAIL

The pass mark of 80 also sits above the hardcoded 0.8 threshold used by
``form_start_page_buttons``, so the start-screen button ("Try Again" vs "Next")
agrees with the results page verdict.

Retakes: a completed attempt does not block a new one -
``learner_progress.attempts.get_or_create_incomplete`` makes a fresh attempt every time the
form is started, so the quiz can be taken repeatedly by visiting
``/courses/<slug>/<index>/start_form`` (the "Retry quiz" button on the results
page points there, and is only rendered after a FAIL).

The course is also registered to the multi-select QA cohort so the attempts
show up in the educator cohort course-progress panel.

Usage:
    uv run python manage.py qa_create_checkbox_scoring_quiz
    uv run python manage.py qa_create_checkbox_scoring_quiz --site-name DemoDev
"""

from typing import cast

import djclick as click

from django.contrib.sites.models import Site

from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
)
from freedom_ls.content_engine.models import Course
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
)
from freedom_ls.form_engine.models import (
    Form,
    FormPage,
    FormQuestion,
    FormStrategy,
    QuestionType,
)
from freedom_ls.qa_helpers.management.commands.qa_create_multiselect_quiz_scoring import (
    _add_member,
    _add_options,
    _get_or_create_cohort,
    _get_or_create_user,
    _register,
    _register_cohort,
)

LEARNER_EMAIL = "demodev_quizqa@email.com"

COURSE_TITLE = "QA Checkbox Scoring Quiz Course"
COURSE_SLUG = "qa-checkbox-scoring-course"

FORM_TITLE = "QA Checkbox Scoring Quiz"
FORM_SLUG = "qa-checkbox-scoring-quiz"
PASS_PERCENTAGE = 80

PAGE_TITLE = "QA Checkbox Scoring Quiz Page"
PAGE_SLUG = "qa-checkbox-scoring-quiz-page"

MC_QUESTION = "Warm up (single-select): which option is correct?"
MC_OPTIONS: list[tuple[str, bool]] = [
    ("Single-select CORRECT option", True),
    ("Single-select wrong option A", False),
    ("Single-select wrong option B", False),
]

CHECKBOX_QUESTION = "Which TWO of these options are correct? (multi-select, optional)"
CHECKBOX_OPTIONS: list[tuple[str, bool]] = [
    ("Checkbox CORRECT 1", True),
    ("Checkbox CORRECT 2", True),
    ("Checkbox WRONG 3", False),
]


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e


def _get_or_create_course(site: Site) -> Course:
    existing: Course | None = Course.objects.filter(slug=COURSE_SLUG, site=site).first()
    if existing is not None:
        return existing
    return cast(
        Course,
        CourseFactory(
            title=COURSE_TITLE,
            slug=COURSE_SLUG,
            description=(
                "QA course holding a scored quiz built from option-backed "
                "questions only, so 100% is reachable."
            ),
            site=site,
        ),
    )


def _build_quiz(site: Site) -> Form:
    """QUIZ form: one required multiple_choice + one optional checkboxes. Idempotent."""
    existing: Form | None = Form.objects.filter(slug=FORM_SLUG, site=site).first()
    if existing is not None:
        return existing

    form = cast(
        Form,
        FormFactory(
            title=FORM_TITLE,
            slug=FORM_SLUG,
            strategy=FormStrategy.QUIZ,
            quiz_show_incorrect=True,
            quiz_pass_percentage=PASS_PERCENTAGE,
            site=site,
        ),
    )
    page = cast(
        FormPage,
        FormPageFactory(
            form=form, title=PAGE_TITLE, slug=PAGE_SLUG, order=0, site=site
        ),
    )

    mc_question = cast(
        FormQuestion,
        FormQuestionFactory(
            form_page=page,
            question=MC_QUESTION,
            type=QuestionType.MULTIPLE_CHOICE,
            required=True,
            order=0,
            site=site,
        ),
    )
    _add_options(mc_question, MC_OPTIONS, site)

    # Optional on purpose: the "tick nothing" row of the scoring matrix cannot be
    # submitted at all while the question is required.
    checkbox_question = cast(
        FormQuestion,
        FormQuestionFactory(
            form_page=page,
            question=CHECKBOX_QUESTION,
            type=QuestionType.CHECKBOXES,
            required=False,
            order=1,
            site=site,
        ),
    )
    _add_options(checkbox_question, CHECKBOX_OPTIONS, site)

    return form


def _attach_form_to_course(course: Course, form: Form, site: Site) -> None:
    already = any(item.child_id == form.pk for item in course.items.all())
    if not already:
        ContentCollectionItemFactory(
            collection_object=course, child_object=form, order=0, site=site
        )


def _item_index(course: Course, form: Form) -> int:
    for i, item in enumerate(course.viewable_items()):
        if isinstance(item, Form) and item.pk == form.pk:
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
    """Seed the clean option-backed scored quiz for checkbox-scoring QA."""
    site = _get_site(site_name)
    learner, created = _get_or_create_user(site, LEARNER_EMAIL, "Quiz", "Scoring QA")

    course = _get_or_create_course(site)
    quiz = _build_quiz(site)
    _attach_form_to_course(course, quiz, site)
    course = cast(Course, Course.objects.get(pk=course.pk))

    _register(learner, course, site)

    cohort = _get_or_create_cohort(site)
    _register_cohort(cohort, course, site)
    _add_member(learner, cohort, site)

    index = _item_index(course, quiz)
    questions = list(
        FormQuestion.objects.filter(form_page__form=quiz).order_by("order")
    )

    click.secho("\n--- Checkbox scoring quiz QA data ---", fg="cyan", bold=True)
    click.secho(f"Site:   {site.name} ({site.domain}) [id {site.pk}]", fg="cyan")
    click.secho(
        f"{'Created' if created else 'Reused'} learner login: "
        f"{learner.email} / {learner.email}",
        fg="green",
        bold=True,
    )
    click.secho(f"Course: {course.title}  [slug: {course.slug}]", fg="cyan", bold=True)
    click.secho(f"  start screen  : /courses/{course.slug}/{index}/", fg="green")
    click.secho(
        f"  runner page 1 : /courses/{course.slug}/{index}/fill_form/1", fg="green"
    )
    click.secho(
        f"  results page  : /courses/{course.slug}/{index}/complete", fg="green"
    )
    click.secho(
        f"  retake (GET)  : /courses/{course.slug}/{index}/start_form", fg="green"
    )

    click.secho("\nQuiz configuration:", fg="cyan", bold=True)
    click.echo(f"  slug                : {quiz.slug}")
    click.echo(f"  strategy            : {quiz.strategy}")
    click.echo(f"  quiz_pass_percentage: {quiz.quiz_pass_percentage}")
    click.echo(f"  quiz_show_incorrect : {quiz.quiz_show_incorrect}")
    click.echo(f"  max_score           : {len(questions)} (all option-backed)")
    for question in questions:
        required = "required" if question.required else "OPTIONAL"
        click.echo(f"  [{question.type}, {required}] {question.question}")
        for option in question.options.order_by("order"):
            mark = "CORRECT" if option.correct else "incorrect"
            click.echo(f"      - {option.text}  [{mark}]")

    click.secho(
        "\nExpected (multiple-choice answered correctly every time):", fg="cyan"
    )
    click.secho("  both correct boxes only -> 2/2 = 100% -> PASS", fg="green")
    click.secho("  any other combination   -> 1/2 =  50% -> FAIL", fg="green")
    click.secho(f"\nCohort for the educator panel: {cohort.name}", fg="cyan")
    click.secho(
        f"  /educator/organisations/{cohort.organisation.slug}/cohorts/{cohort.pk}",
        fg="green",
    )
