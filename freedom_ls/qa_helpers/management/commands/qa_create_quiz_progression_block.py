"""Seed a course where a FAILED quiz blocks progression to the NEXT item.

The existing multi-select scoring fixtures
(``qa_create_form_question_types`` / ``qa_create_multiselect_quiz_scoring``)
build single-item courses, so there is no following item for a failed quiz to
block. ``get_content_status`` in ``freedom_ls/learner_interface/utils.py``
returns ``(FAILED, BLOCKED)`` for a completed quiz the learner did not pass,
and that ``BLOCKED`` is what the *next* item inherits -- only visible when the
quiz has a successor.

This command builds (idempotently) a three-item course:

1. Topic  -- pre-completed for the QA learner so the quiz is immediately READY.
2. QUIZ Form -- ``quiz_show_incorrect=True``, ``quiz_pass_percentage=80``,
   four option-backed questions: three ``multiple_choice`` (1 correct of 3) and
   one ``checkboxes`` (3 options, exactly 2 correct).
3. Topic  -- the successor that must stay locked until the quiz is passed.

The pass arithmetic is chosen so the checkbox question alone decides the
verdict, with every multiple-choice question answered correctly:

* checkbox correct  -> 4/4 = 100% >= 80  -> PASS  -> item 3 unlocks
* checkbox wrong    -> 3/4 =  75% <  80  -> FAIL  -> item 3 stays BLOCKED

Only option-backed questions are used: ``FormProgress.score_quiz()`` counts
every question toward ``max_score`` and free-text questions can never be scored
correct, so a quiz holding one could never reach 100%.

The QA learner is deliberately left with NO ``FormProgress`` so the quiz start
screen offers "Start Form" from a clean state.

Usage:
    uv run python manage.py qa_create_quiz_progression_block
    uv run python manage.py qa_create_quiz_progression_block --site-name DemoDev
"""

from typing import cast

import djclick as click

from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import Course, Topic
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
from freedom_ls.learner_progress.factories import TopicProgressFactory
from freedom_ls.learner_progress.models import TopicProgress
from freedom_ls.qa_helpers.management.commands.qa_create_multiselect_quiz_scoring import (
    _add_options,
    _ensure_course_progress_row,
    _get_or_create_user,
    _register,
)
from freedom_ls.qa_helpers.management.commands.qa_create_report_course import (
    _lay_out_course,
)

LEARNER_EMAIL = "demodev_quizqa@email.com"

COURSE_TITLE = "QA Quiz Progression Block Course"
COURSE_SLUG = "qa-progression-block-course"

FIRST_TOPIC_TITLE = "QA Progression Block: Before The Quiz"
FIRST_TOPIC_SLUG = "qa-progression-block-topic-01"
FIRST_TOPIC_CONTENT = (
    "# Before the quiz\n\n"
    "This topic is item 1 of the quiz-progression-block QA course. It is "
    "pre-completed for the QA learner so the quiz at item 2 is immediately "
    "reachable.\n\n"
    "Item 3 (another topic) must stay locked until the quiz at item 2 is "
    "**passed**.\n"
)

NEXT_TOPIC_TITLE = "QA Progression Block: After The Quiz"
NEXT_TOPIC_SLUG = "qa-progression-block-topic-02"
NEXT_TOPIC_CONTENT = (
    "# After the quiz\n\n"
    "If you can read this, the quiz at item 2 was passed. Failing that quiz "
    "must leave this topic BLOCKED (locked icon, no link) in the course "
    "index.\n"
)

FORM_TITLE = "QA Progression Block Quiz"
FORM_SLUG = "qa-progression-block-quiz"
PASS_PERCENTAGE = 80

PAGE_TITLE = "QA Progression Block Quiz Page"
PAGE_SLUG = "qa-progression-block-quiz-page"

CHECKBOX_QUESTION = "Which TWO of these unlock the next course item? (multi-select)"
CHECKBOX_OPTIONS: list[tuple[str, bool]] = [
    ("Correct box 1 - tick me", True),
    ("Correct box 2 - tick me", True),
    ("Wrong box - leave me alone", False),
]

# (question stem, options). Each single-select question has exactly one correct
# option, so answering all three correctly is worth 3 of the 4 marks - one mark
# short of the 80% pass mark, which the checkboxes question supplies.
MC_QUESTIONS: list[str] = [
    "Single-select warm up 1: pick the correct answer",
    "Single-select warm up 2: pick the correct answer",
    "Single-select warm up 3: pick the correct answer",
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
                "QA course for checking that a failed quiz blocks progression "
                "to the next course item."
            ),
            site=site,
        ),
    )


def _get_or_create_topic(site: Site, title: str, slug: str, content: str) -> Topic:
    existing: Topic | None = Topic.objects.filter(slug=slug, site=site).first()
    if existing is not None:
        return existing
    return cast(
        Topic,
        TopicFactory(title=title, slug=slug, content=content, site=site),
    )


def _build_quiz(site: Site) -> Form:
    """QUIZ form whose checkboxes question decides pass/fail. Idempotent."""
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

    for order, stem in enumerate(MC_QUESTIONS):
        question = cast(
            FormQuestion,
            FormQuestionFactory(
                form_page=page,
                question=stem,
                type=QuestionType.MULTIPLE_CHOICE,
                required=True,
                order=order,
                site=site,
            ),
        )
        _add_options(
            question,
            [
                (f"Correct answer (Q{order + 1})", True),
                (f"Wrong answer A (Q{order + 1})", False),
                (f"Wrong answer B (Q{order + 1})", False),
            ],
            site,
        )

    # The decider: last question, 3 options, exactly 2 correct.
    checkbox_question = cast(
        FormQuestion,
        FormQuestionFactory(
            form_page=page,
            question=CHECKBOX_QUESTION,
            type=QuestionType.CHECKBOXES,
            required=True,
            order=len(MC_QUESTIONS),
            site=site,
        ),
    )
    _add_options(checkbox_question, CHECKBOX_OPTIONS, site)

    return form


def _complete_topic(user: User, topic: Topic, site: Site) -> None:
    """Mark a topic complete for the learner.

    The ``CourseItemProgress`` save hook only fires on a None -> set transition,
    so the row is created first and ``complete_time`` assigned afterwards.
    """
    progress: TopicProgress | None = TopicProgress.objects.filter(
        user=user, topic=topic, site=site
    ).first()
    if progress is None:
        progress = cast(
            TopicProgress, TopicProgressFactory(user=user, topic=topic, site=site)
        )
    if progress.complete_time is None:
        progress.complete_time = timezone.now()
        progress.save()


def _item_index(course: Course, item: Topic | Form) -> int:
    for i, viewable in enumerate(course.viewable_items()):
        if type(viewable) is type(item) and viewable.pk == item.pk:
            return i + 1
    raise click.ClickException(
        f"'{item.slug}' is not a viewable item of course '{course.slug}'."
    )


@click.command()
@click.option(
    "--site-name",
    default="DemoDev",
    help="Site name to create the data on (default: 'DemoDev').",
)
def command(site_name: str) -> None:
    """Seed the failed-quiz-blocks-next-item browser-QA course and its learner."""
    site = _get_site(site_name)
    learner, created = _get_or_create_user(site, LEARNER_EMAIL, "Quiz", "Scoring QA")

    course = _get_or_create_course(site)
    first_topic = _get_or_create_topic(
        site, FIRST_TOPIC_TITLE, FIRST_TOPIC_SLUG, FIRST_TOPIC_CONTENT
    )
    quiz = _build_quiz(site)
    next_topic = _get_or_create_topic(
        site, NEXT_TOPIC_TITLE, NEXT_TOPIC_SLUG, NEXT_TOPIC_CONTENT
    )
    # Every link is written before any viewable_items() read: Course.children()
    # is memoized per instance, so a link created after a read reports stale.
    _lay_out_course(course, [first_topic, quiz, next_topic], site)
    course = cast(Course, Course.objects.get(pk=course.pk))

    _register(learner, course, site)
    _ensure_course_progress_row(learner, course, site)
    # Item 1 complete => item 2 (the quiz) is READY; the quiz itself is left
    # untouched so the start screen shows "Start Form".
    _complete_topic(learner, first_topic, site)

    indexes = {
        "first_topic": _item_index(course, first_topic),
        "quiz": _item_index(course, quiz),
        "next_topic": _item_index(course, next_topic),
    }
    question_count = FormQuestion.objects.filter(form_page__form=quiz).count()

    click.secho("\n--- Failed-quiz progression block QA data ---", fg="cyan", bold=True)
    click.secho(f"Site:   {site.name} ({site.domain}) [id {site.pk}]", fg="cyan")
    click.secho(
        f"{'Created' if created else 'Reused'} learner login: "
        f"{learner.email} / {learner.email}",
        fg="green",
        bold=True,
    )
    click.secho(f"Course: {course.title}  [slug: {course.slug}]", fg="cyan", bold=True)
    click.secho(f"  /courses/{course.slug}/", fg="green")
    click.secho("Items, in order:", fg="cyan")
    click.secho(
        f"  {indexes['first_topic']}. [Topic] {first_topic.title}  "
        f"-> /courses/{course.slug}/{indexes['first_topic']}/  (pre-completed)",
        fg="green",
    )
    click.secho(
        f"  {indexes['quiz']}. [Quiz ] {quiz.title}  "
        f"-> /courses/{course.slug}/{indexes['quiz']}/  (start screen)",
        fg="green",
    )
    click.secho(
        f"        runner page 1 -> "
        f"/courses/{course.slug}/{indexes['quiz']}/fill_form/1",
        fg="green",
    )
    click.secho(
        f"  {indexes['next_topic']}. [Topic] {next_topic.title}  "
        f"-> /courses/{course.slug}/{indexes['next_topic']}/  "
        f"(must be BLOCKED after a failed quiz)",
        fg="green",
    )

    click.secho("\nQuiz configuration:", fg="cyan", bold=True)
    click.echo(f"  slug                : {quiz.slug}")
    click.echo(f"  strategy            : {quiz.strategy}")
    click.echo(f"  quiz_pass_percentage: {quiz.quiz_pass_percentage}")
    click.echo(f"  quiz_show_incorrect : {quiz.quiz_show_incorrect}")
    click.echo(f"  questions           : {question_count} (all option-backed)")
    for question in FormQuestion.objects.filter(form_page__form=quiz).order_by("order"):
        click.echo(f"  [{question.type}] {question.question}")
        for option in question.options.order_by("order"):
            mark = "CORRECT" if option.correct else "incorrect"
            click.echo(f"      - {option.text}  [{mark}]")

    click.secho(
        "\nExpected arithmetic (all single-select answered correctly):", fg="cyan"
    )
    click.secho(
        f"  checkbox CORRECT (both correct boxes, nothing else): "
        f"{question_count}/{question_count} = 100% >= {PASS_PERCENTAGE} -> PASS "
        f"-> item {indexes['next_topic']} unlocks",
        fg="green",
    )
    click.secho(
        f"  checkbox WRONG   (e.g. only the wrong box ticked)  : "
        f"{question_count - 1}/{question_count} = "
        f"{round((question_count - 1) / question_count * 100)}% < {PASS_PERCENTAGE} "
        f"-> FAIL -> item {indexes['next_topic']} stays BLOCKED",
        fg="green",
    )
