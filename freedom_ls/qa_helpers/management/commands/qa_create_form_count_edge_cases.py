"""Seed the two counting edge cases for the form start page.

``learner_interface/templates/learner_interface/course_form.html`` renders two
fact pills built from ``count_form_questions(form)`` and ``form.pages.count()``,
pluralised with the ``pluralize`` filter. Every existing form fixture has two or
more questions, so the singular ("1 question" / "1 page") and empty
("0 questions" / "0 pages") renderings are unreachable in the browser.

This command builds, idempotently, one single-item course per case:

1. ``qa-single-question-course`` -- a QUIZ with exactly ONE page holding exactly
   ONE ``multiple_choice`` question, so the pills must read "1 question" and
   "1 page".
2. ``qa-empty-form-course`` -- a form with ZERO pages and therefore ZERO
   questions, so the pills must read "0 questions" and "0 pages". Nothing in the
   data model requires a form to own a page: ``FormPage.form`` is an ordinary FK
   with no minimum, and ``Form`` declares only ``unique_form_slug_per_site``.

Both forms deliberately carry a plain title, an empty subtitle and empty
markdown content -- the title/subtitle/intro variations are QA'd separately.

The empty form is CATEGORY_VALUE_SUM rather than QUIZ: a pageless quiz would
score 0 out of 0 questions if anyone completed it, and the point of the fixture
is the start screen, not the scorer.

Registration for ``demodev_quizqa@email.com`` (password == email) is created for
both courses so the start pages open without an access redirect.

Usage:
    uv run python manage.py qa_create_form_count_edge_cases
    uv run python manage.py qa_create_form_count_edge_cases --site-name DemoDev
"""

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
    FormQuestion,
    FormStrategy,
    QuestionType,
)
from freedom_ls.form_engine.queries import count_form_questions
from freedom_ls.qa_helpers.management.commands.qa_create_multiselect_quiz_scoring import (
    _add_options,
    _get_or_create_user,
    _register,
)
from freedom_ls.qa_helpers.management.commands.qa_create_report_course import (
    _lay_out_course,
)

LEARNER_EMAIL = "demodev_quizqa@email.com"

SINGLE_COURSE_TITLE = "QA Single Question Course"
SINGLE_COURSE_SLUG = "qa-single-question-course"
SINGLE_FORM_TITLE = "Single Question Quiz"
SINGLE_FORM_SLUG = "qa-single-question-form"
SINGLE_PAGE_TITLE = "The Only Page"
SINGLE_PAGE_SLUG = "qa-single-question-page"
SINGLE_PASS_PERCENTAGE = 50

SINGLE_QUESTION = "Which of these is the only question in this form?"
SINGLE_QUESTION_OPTIONS: list[tuple[str, bool]] = [
    ("This one - it is the only question", True),
    ("A second question that does not exist", False),
    ("A third question that does not exist", False),
]

EMPTY_COURSE_TITLE = "QA Empty Form Course"
EMPTY_COURSE_SLUG = "qa-empty-form-course"
EMPTY_FORM_TITLE = "Empty Form"
EMPTY_FORM_SLUG = "qa-empty-form"


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e


def _get_or_create_course(
    site: Site, title: str, slug: str, description: str
) -> Course:
    existing: Course | None = Course.objects.filter(slug=slug, site=site).first()
    if existing is not None:
        return existing
    return cast(
        Course,
        CourseFactory(title=title, slug=slug, description=description, site=site),
    )


def _build_single_question_form(site: Site) -> Form:
    """QUIZ with exactly one page holding exactly one question. Idempotent."""
    existing: Form | None = Form.objects.filter(
        slug=SINGLE_FORM_SLUG, site=site
    ).first()
    if existing is not None:
        return existing

    form = cast(
        Form,
        FormFactory(
            title=SINGLE_FORM_TITLE,
            subtitle="",
            content="",
            slug=SINGLE_FORM_SLUG,
            strategy=FormStrategy.QUIZ,
            quiz_show_incorrect=True,
            quiz_pass_percentage=SINGLE_PASS_PERCENTAGE,
            site=site,
        ),
    )
    page = cast(
        FormPage,
        FormPageFactory(
            form=form,
            title=SINGLE_PAGE_TITLE,
            slug=SINGLE_PAGE_SLUG,
            order=0,
            site=site,
        ),
    )
    question = cast(
        FormQuestion,
        FormQuestionFactory(
            form_page=page,
            question=SINGLE_QUESTION,
            type=QuestionType.MULTIPLE_CHOICE,
            required=True,
            order=0,
            site=site,
        ),
    )
    _add_options(question, SINGLE_QUESTION_OPTIONS, site)
    return form


def _build_empty_form(site: Site) -> Form:
    """Form with no pages and therefore no questions. Idempotent."""
    existing: Form | None = Form.objects.filter(slug=EMPTY_FORM_SLUG, site=site).first()
    if existing is not None:
        return existing

    return cast(
        Form,
        FormFactory(
            title=EMPTY_FORM_TITLE,
            subtitle="",
            content="",
            slug=EMPTY_FORM_SLUG,
            strategy=FormStrategy.CATEGORY_VALUE_SUM,
            quiz_show_incorrect=None,
            quiz_pass_percentage=None,
            site=site,
        ),
    )


def _item_index(course: Course, form: Form) -> int:
    for i, item in enumerate(course.viewable_items()):
        if isinstance(item, Form) and item.pk == form.pk:
            return i + 1
    raise click.ClickException(
        f"Form '{form.slug}' is not a viewable item of course '{course.slug}'."
    )


def _report(course: Course, form: Form, index: int) -> None:
    question_count = count_form_questions(form)
    page_count = form.pages.count()
    click.secho(f"Course: {course.title}  [slug: {course.slug}]", fg="cyan", bold=True)
    click.secho(
        f"Form:   {form.title}  [slug: {form.slug}, strategy: {form.strategy}]",
        fg="cyan",
    )
    click.echo(f"  subtitle            : {form.subtitle!r}")
    click.echo(f"  content             : {form.content!r}")
    click.echo(f"  quiz_pass_percentage: {form.quiz_pass_percentage}")
    click.echo(f"  pages               : {page_count}")
    click.echo(f"  questions           : {question_count}")
    click.secho(
        f"  Start page pills    : "
        f"'{question_count} question{'' if question_count == 1 else 's'}' / "
        f"'{page_count} page{'' if page_count == 1 else 's'}'",
        fg="yellow",
    )
    click.secho(f"  Start page URL      : /courses/{course.slug}/{index}/", fg="green")


@click.command()
@click.option(
    "--site-name",
    default="DemoDev",
    help="Site name to create the data on (default: 'DemoDev').",
)
def command(site_name: str) -> None:
    """Seed the 1-question and 0-question form start-page fixtures."""
    site = _get_site(site_name)
    learner, created = _get_or_create_user(site, LEARNER_EMAIL, "Quiz", "Scoring QA")

    single_course = _get_or_create_course(
        site,
        SINGLE_COURSE_TITLE,
        SINGLE_COURSE_SLUG,
        "QA course whose only item is a form with exactly one question.",
    )
    single_form = _build_single_question_form(site)
    _lay_out_course(single_course, [single_form], site)
    single_course = cast(Course, Course.objects.get(pk=single_course.pk))

    empty_course = _get_or_create_course(
        site,
        EMPTY_COURSE_TITLE,
        EMPTY_COURSE_SLUG,
        "QA course whose only item is a form with no pages and no questions.",
    )
    empty_form = _build_empty_form(site)
    _lay_out_course(empty_course, [empty_form], site)
    empty_course = cast(Course, Course.objects.get(pk=empty_course.pk))

    _register(learner, single_course, site)
    _register(learner, empty_course, site)

    click.secho(
        "\n--- Form start-page counting edge cases ---",
        fg="cyan",
        bold=True,
    )
    click.secho(f"Site:   {site.name} ({site.domain}) [id {site.pk}]", fg="cyan")
    click.secho(
        f"{'Created' if created else 'Reused'} learner login: "
        f"{learner.email} / {learner.email}",
        fg="green",
        bold=True,
    )

    click.secho("\n1. Singular case", fg="cyan", bold=True)
    _report(single_course, single_form, _item_index(single_course, single_form))

    click.secho("\n2. Empty case", fg="cyan", bold=True)
    _report(empty_course, empty_form, _item_index(empty_course, empty_form))
    click.secho(
        "   NOTE: the empty form has no page to fill in, so following its "
        "'Start Form' button ends in a 404 from form_fill_page.",
        fg="yellow",
    )
