"""Seed a one-form course that exercises the question legend's edge cases.

``learner_interface/course_form_page.html`` renders each question inside a
``<legend>`` that has to do three awkward things at once: float the question
number beside the first line, keep the required asterisk glued to the question's
last word (via ``&nbsp;``), and inline **only** the last rendered paragraph so a
multi-paragraph question still reads as separate paragraphs. Every existing
demo/QA form has short, single-paragraph, unformatted question text, so none of
those branches wrap or separate in a browser.

This command builds (idempotently) a single-item course whose only viewable item
is a QUIZ Form with one page holding exactly four questions, in order:

1. required, markdown-rich (bold / italic / inline code / link) and long enough
   to wrap over two or three lines at desktop width.
2. NOT required, short -- must render with no asterisk at all.
3. required, two markdown paragraphs -- number beside the first line, asterisk
   on the last word of the *second* paragraph, paragraphs visually distinct.
4. required, one 78-word unformatted paragraph -- wraps at any viewport.

The learner ``demodev@email.com`` is registered for the course and left with no
``FormProgress``, so the form is in its never-opened state.

The login convention in this project is password == email address.

Usage:
    uv run python manage.py qa_create_legend_edge_cases
    uv run python manage.py qa_create_legend_edge_cases --site-name DemoDev
"""

from dataclasses import dataclass, field
from typing import cast

import djclick as click

from django.contrib.sites.models import Site

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
)
from freedom_ls.form_engine.models import (
    Form,
    FormPage,
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionType,
)
from freedom_ls.qa_helpers.management.commands.qa_create_form_question_types import (
    LEARNER_EMAIL,
    _get_learner,
    _get_site,
)
from freedom_ls.qa_helpers.management.commands.qa_create_multiselect_quiz_scoring import (
    _add_options,
    _item_index,
    _register,
)
from freedom_ls.qa_helpers.management.commands.qa_create_report_course import (
    _lay_out_course,
)

COURSE_TITLE = "QA Legend Edge Cases"
COURSE_SLUG = "qa-legend-edge-cases"
COURSE_DESCRIPTION = (
    "QA course whose only item is a form built to stress the question legend: "
    "wrapping question text, inline markdown, a multi-paragraph question and an "
    "optional question with no asterisk."
)
COURSE_ACCESS_CONFIG: dict[str, str] = {"access_type": "free"}

FORM_TITLE = "QA Legend Edge Cases Form"
FORM_SLUG = "qa-legend-edge-cases-form"
PASS_PERCENTAGE = 50

PAGE_TITLE = "QA Legend Edge Cases Page"
PAGE_SLUG = "qa-legend-edge-cases-page"


@dataclass(frozen=True)
class QuestionSpec:
    """One planned question: its markdown body, type, flag and options."""

    question: str
    type: QuestionType
    required: bool
    note: str
    options: tuple[tuple[str, bool], ...] = field(default_factory=tuple)


# 1. Required + inline markdown + long enough to wrap (38 words).
Q1_MARKDOWN = (
    "When you **submit this form** the runner validates every *required* answer "
    "server-side before it writes anything, so which of the following best "
    "describes what the `required` flag on a question actually does, according "
    "to the [form engine notes](https://example.com/fls/form-engine)?"
)

# 3. Required + two markdown paragraphs (blank line between them).
Q3_MARKDOWN = (
    "A form question's markdown body may contain more than one paragraph, and "
    "the legend has to keep those paragraphs visually separate rather than "
    "letting them run together into a single block of text.\n\n"
    "The question number should sit beside the first line of the first "
    "paragraph, while the required asterisk belongs on the very last word of "
    "this second paragraph. Which of those two placements are you checking "
    "right now?"
)

# 4. Required + one long unformatted paragraph (78 words).
Q4_MARKDOWN = (
    "This question exists purely so that its text is long enough to wrap across "
    "several lines at any viewport width you are likely to test, from a narrow "
    "phone in portrait orientation all the way up to a very wide desktop "
    "monitor, and the only thing you need to confirm is that the red asterisk "
    "marking the question as required stays attached to the final word of the "
    "paragraph instead of wrapping onto a line of its own."
)

QUESTION_PLAN: list[QuestionSpec] = [
    QuestionSpec(
        question=Q1_MARKDOWN,
        type=QuestionType.MULTIPLE_CHOICE,
        required=True,
        note="required + inline markdown (bold/italic/code/link), wraps 2-3 lines",
        options=(
            ("It blocks submission until the question is answered", True),
            ("It only changes the colour of the label", False),
        ),
    ),
    QuestionSpec(
        question="Anything to add here? (This one is optional.)",
        type=QuestionType.SHORT_TEXT,
        required=False,
        note="NOT required -- must show no asterisk",
    ),
    QuestionSpec(
        question=Q3_MARKDOWN,
        type=QuestionType.MULTIPLE_CHOICE,
        required=True,
        note="required + two markdown paragraphs",
        options=(
            ("The number beside the first line", True),
            ("The asterisk on the last word of the second paragraph", False),
        ),
    ),
    QuestionSpec(
        question=Q4_MARKDOWN,
        type=QuestionType.MULTIPLE_CHOICE,
        required=True,
        note="required + 78-word single paragraph, wraps at any width",
        options=(
            ("The asterisk stayed on the last word", True),
            ("The asterisk wrapped onto its own line", False),
        ),
    ),
]


def _get_or_create_course(site: Site) -> Course:
    """Create the course, or refresh an existing one's title/access config."""
    existing: Course | None = Course.objects.filter(slug=COURSE_SLUG, site=site).first()
    if existing is not None:
        existing.title = COURSE_TITLE
        existing.access_config = COURSE_ACCESS_CONFIG
        existing.save(update_fields=["title", "access_config"])
        return existing
    return cast(
        Course,
        CourseFactory(
            title=COURSE_TITLE,
            slug=COURSE_SLUG,
            description=COURSE_DESCRIPTION,
            access_config=COURSE_ACCESS_CONFIG,
            site=site,
        ),
    )


def _get_or_create_form(site: Site) -> Form:
    existing: Form | None = Form.objects.filter(slug=FORM_SLUG, site=site).first()
    if existing is not None:
        return existing
    return cast(
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


def _get_or_create_page(form: Form, site: Site) -> FormPage:
    existing: FormPage | None = FormPage.objects.filter(
        form=form, slug=PAGE_SLUG, site=site
    ).first()
    if existing is not None:
        return existing
    return cast(
        FormPage,
        FormPageFactory(
            form=form, title=PAGE_TITLE, slug=PAGE_SLUG, order=0, site=site
        ),
    )


def _sync_questions(page: FormPage, site: Site) -> list[FormQuestion]:
    """Bring the page's questions in line with QUESTION_PLAN. Idempotent.

    Questions are matched on ``order``, so a re-run rewrites the wording,
    type and required flag of an earlier run rather than appending duplicates.
    """
    questions: list[FormQuestion] = []
    for order, spec in enumerate(QUESTION_PLAN):
        existing: FormQuestion | None = FormQuestion.objects.filter(
            form_page=page, order=order, site=site
        ).first()
        if existing is None:
            question = cast(
                FormQuestion,
                FormQuestionFactory(
                    form_page=page,
                    question=spec.question,
                    type=spec.type,
                    required=spec.required,
                    order=order,
                    site=site,
                ),
            )
        else:
            question = existing
            question.question = spec.question
            question.type = spec.type
            question.required = spec.required
            question.save(update_fields=["question", "type", "required"])
        if spec.options and not question.options.exists():
            _add_options(question, list(spec.options), site)
        questions.append(question)

    # Drop anything a previous, longer plan left behind on this page.
    FormQuestion.objects.filter(form_page=page, site=site).exclude(
        pk__in=[q.pk for q in questions]
    ).delete()
    return questions


@click.command()
@click.option(
    "--site-name",
    default="DemoDev",
    help="Site name to create the data on (default: 'DemoDev').",
)
def command(site_name: str) -> None:
    """Seed the legend edge-case QA course and register the learner."""
    site = _get_site(site_name)
    learner = _get_learner(site)

    course = _get_or_create_course(site)
    form = _get_or_create_form(site)
    page = _get_or_create_page(form, site)
    questions = _sync_questions(page, site)
    # Every link is written before any viewable_items() read: Course.children()
    # is memoized per instance, so a link created after a read reports stale.
    _lay_out_course(course, [form], site)
    course = cast(Course, Course.objects.get(pk=course.pk))

    _register(learner, course, site)

    form_index = _item_index(course, form)
    attempts = FormProgress.objects.filter(form=form, user=learner).count()

    click.secho("\n--- Legend edge-case QA course ---", fg="cyan", bold=True)
    click.secho(f"Site:   {site.name} ({site.domain}) [id {site.pk}]", fg="cyan")
    click.secho(f"Login:  {LEARNER_EMAIL} / {LEARNER_EMAIL}", fg="green", bold=True)
    click.secho(f"Course: {course.title}  [slug: {course.slug}]", fg="cyan", bold=True)
    click.secho(f"  visibility={course.visibility}", fg="cyan")
    click.secho(f"  access_config={course.access_config}", fg="cyan")
    click.secho(f"  /courses/{course.slug}/", fg="green")
    click.secho(
        f"  start page -> /courses/{course.slug}/{form_index}/",
        fg="green",
    )
    click.secho(
        f"  runner     -> /courses/{course.slug}/{form_index}/fill_form/1",
        fg="green",
        bold=True,
    )
    click.secho("\nQuestions on the single page, in order:", fg="cyan", bold=True)
    for spec, question in zip(QUESTION_PLAN, questions, strict=True):
        flag = "REQUIRED" if question.required else "optional"
        click.secho(f"  {question.question_number()}. [{flag}] {spec.note}", fg="green")
        click.echo(f"        type={question.type}  words={len(spec.question.split())}")
    click.secho("\nForm configuration:", fg="cyan", bold=True)
    click.echo(f"  slug                : {form.slug}")
    click.echo(f"  strategy            : {form.strategy}")
    click.echo(f"  quiz_pass_percentage: {form.quiz_pass_percentage}")
    click.echo(f"  pages               : {form.pages.count()}")
    click.echo(f"  questions           : {len(questions)}")
    click.echo(f"  FormProgress rows for {learner.email}: {attempts}")
