"""Seed a course whose FIRST viewable item is a Form, not a Topic.

The course player's form start page (``learner_interface/course_form.html``)
renders its "Previous" button only when ``previous_url`` is set, i.e. only when
the form has a preceding item. Every demo course begins with a Topic or a
CoursePart, so the "form at index 1 => no Previous button" branch could not be
exercised in a browser. The pytest equivalent is
``test_first_item_form_start_page_has_no_previous_button`` in
``freedom_ls/learner_interface/tests/test_course_item_navigation.py``.

This command builds (idempotently) a two-item course:

1. Form  -- a QUIZ with a single multiple-choice question, so the start page
   renders with NO "Previous" button (nothing precedes it).
2. Topic -- the successor, so the form is not also the last item and the
   forward button is a real "Next" rather than "Finish course".

The learner ``demodev@email.com`` is registered for the course and left with no
``FormProgress``, so the start screen offers "Start Form" from a clean state.
Item 1 is always READY under the sequential-unlock rule, so nothing has to be
pre-completed.

The login convention in this project is password == email address.

Usage:
    uv run python manage.py qa_create_form_first_course
    uv run python manage.py qa_create_form_first_course --site-name DemoDev
"""

from typing import cast

import djclick as click

from django.contrib.sites.models import Site

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
    _register,
)
from freedom_ls.qa_helpers.management.commands.qa_create_report_course import (
    _lay_out_course,
)

COURSE_TITLE = "QA Form First Course"
COURSE_SLUG = "qa-form-first-course"
COURSE_ACCESS_CONFIG: dict[str, str] = {"access_type": "free"}

FORM_TITLE = "QA Form First Form"
FORM_SLUG = "qa-form-first-form"
PASS_PERCENTAGE = 50

PAGE_TITLE = "QA Form First Page"
PAGE_SLUG = "qa-form-first-page"

MC_QUESTION = "Does this form have anything before it in the course?"
MC_OPTIONS: list[tuple[str, bool]] = [
    ("No - it is item 1, so there is no Previous button", True),
    ("Yes - there is a topic before it", False),
    ("Impossible to say", False),
]

TOPIC_TITLE = "QA Form First: After The Form"
TOPIC_SLUG = "qa-form-first-topic-02"
TOPIC_CONTENT = (
    "# After the form\n\n"
    "This topic exists so the form at item 1 is not also the *last* item of "
    "the course. The form's start page must therefore show a forward button "
    "and **no** Previous button.\n"
)


def _get_or_create_course(site: Site) -> Course:
    """Create the course, or refresh an existing one's access config."""
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
            description=(
                "QA course whose very first content item is a form, so the "
                "form start page's no-Previous-button branch is reachable in "
                "a browser."
            ),
            access_config=COURSE_ACCESS_CONFIG,
            site=site,
        ),
    )


def _get_or_create_topic(site: Site) -> Topic:
    existing: Topic | None = Topic.objects.filter(slug=TOPIC_SLUG, site=site).first()
    if existing is not None:
        return existing
    return cast(
        Topic,
        TopicFactory(
            title=TOPIC_TITLE, slug=TOPIC_SLUG, content=TOPIC_CONTENT, site=site
        ),
    )


def _build_form(site: Site) -> Form:
    """QUIZ form with one page and one multiple-choice question. Idempotent."""
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
    question = cast(
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
    _add_options(question, MC_OPTIONS, site)
    return form


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
    """Seed the form-at-index-1 browser-QA course and register the learner."""
    site = _get_site(site_name)
    learner = _get_learner(site)

    course = _get_or_create_course(site)
    form = _build_form(site)
    topic = _get_or_create_topic(site)
    # Every link is written before any viewable_items() read: Course.children()
    # is memoized per instance, so a link created after a read reports stale.
    _lay_out_course(course, [form, topic], site)
    course = cast(Course, Course.objects.get(pk=course.pk))

    _register(learner, course, site)

    form_index = _item_index(course, form)
    topic_index = _item_index(course, topic)
    question_count = FormQuestion.objects.filter(form_page__form=form).count()
    attempts = FormProgress.objects.filter(form=form, user=learner).count()

    click.secho("\n--- Form-at-index-1 QA course ---", fg="cyan", bold=True)
    click.secho(f"Site:   {site.name} ({site.domain}) [id {site.pk}]", fg="cyan")
    click.secho(f"Login:  {LEARNER_EMAIL} / {LEARNER_EMAIL}", fg="green", bold=True)
    click.secho(f"Course: {course.title}  [slug: {course.slug}]", fg="cyan", bold=True)
    click.secho(f"  visibility={course.visibility}", fg="cyan")
    click.secho(f"  access_config={course.access_config}", fg="cyan")
    click.secho(f"  /courses/{course.slug}/", fg="green")
    click.secho("Items, in order:", fg="cyan")
    click.secho(
        f"  {form_index}. [Form ] {form.title}  "
        f"-> /courses/{course.slug}/{form_index}/  "
        "(start page; must show NO Previous button)",
        fg="green",
    )
    click.secho(
        f"        runner page 1 -> /courses/{course.slug}/{form_index}/fill_form/1",
        fg="green",
    )
    click.secho(
        f"  {topic_index}. [Topic] {topic.title}  "
        f"-> /courses/{course.slug}/{topic_index}/  "
        "(successor, so the form is not the last item)",
        fg="green",
    )
    click.secho("\nForm configuration:", fg="cyan", bold=True)
    click.echo(f"  slug                : {form.slug}")
    click.echo(f"  strategy            : {form.strategy}")
    click.echo(f"  quiz_pass_percentage: {form.quiz_pass_percentage}")
    click.echo(f"  questions           : {question_count}")
    click.echo(f"  FormProgress rows for {learner.email}: {attempts}")
