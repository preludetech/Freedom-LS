"""Seed a NON-scored questionnaire containing free-text questions.

QA 12.4 needs a ``short_text`` / ``long_text`` question answered **in a form
that produces no mark**. FLS has exactly two ``Form.strategy`` values —
``QUIZ`` and ``CATEGORY_VALUE_SUM`` — so ``CATEGORY_VALUE_SUM`` is the
questionnaire/survey strategy (it is what the demo ``course-feedback`` form
uses). Its scorer, ``FormProgress.score_category_value_sum()``, only ever looks
at ``multiple_choice`` questions, and the completion template branches on
``strategy == "QUIZ"`` for every piece of pass/fail and incorrect-answer
markup — so a CATEGORY_VALUE_SUM form built purely from free-text questions
completes with no score, no verdict and no answer review at all.

Builds, idempotently, on the requested site:

1. A dedicated course whose only viewable item is that survey form.
2. A two-page survey: page 1 holds a required ``short_text`` and a required
   ``long_text`` question, page 2 holds an optional one of each. Two pages so
   the runner's "Previous" link is available and QA can walk back to page 1 and
   see the saved free-text answers rendered into the input / textarea.
3. Registration for the existing QA learner (``demodev_quizqa@email.com``,
   password == email), created here if missing.

Usage:
    uv run python manage.py qa_create_free_text_survey
    uv run python manage.py qa_create_free_text_survey --site-name DemoDev
"""

from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
)
from freedom_ls.content_engine.models import (
    Course,
    Form,
    FormPage,
    FormQuestion,
    FormStrategy,
    QuestionType,
)
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.learner_management.models import LearnerCourseRegistration
from freedom_ls.organisations.utils import get_default_organisation

LEARNER_EMAIL = "demodev_quizqa@email.com"

COURSE_TITLE = "QA Free Text Survey Course"
COURSE_SLUG = "qa-free-text-survey-course"

FORM_TITLE = "QA Free Text Survey"
FORM_SLUG = "qa-free-text-survey-form"

PAGE_CATEGORY = "Course Feedback"

# (page title, page slug, [(question text, type, required)])
SURVEY_PAGES: list[tuple[str, str, list[tuple[str, str, bool]]]] = [
    (
        "Your Experience",
        "qa-free-text-survey-page-1",
        [
            (
                "In one line, what was the most useful thing you learned?",
                QuestionType.SHORT_TEXT,
                True,
            ),
            (
                "In your own words, how would you explain this course to a colleague?",
                QuestionType.LONG_TEXT,
                True,
            ),
        ],
    ),
    (
        "Anything Else",
        "qa-free-text-survey-page-2",
        [
            (
                "If you could change one thing about this course, what would it be?",
                QuestionType.SHORT_TEXT,
                False,
            ),
            (
                "Any other comments for the course team?",
                QuestionType.LONG_TEXT,
                False,
            ),
        ],
    ),
]


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e


def _get_or_create_learner(site: Site) -> tuple[User, bool]:
    """Login-ready QA learner (password == email), reused if already present."""
    existing: User | None = User.objects.filter(email=LEARNER_EMAIL).first()
    if existing is not None:
        existing.is_active = True
        existing.set_password(LEARNER_EMAIL)
        existing.save(update_fields=["is_active", "password"])
        learner, created = existing, False
    else:
        learner = cast(
            User,
            UserFactory(
                email=LEARNER_EMAIL,
                first_name="Quiz",
                last_name="Scoring QA",
                is_active=True,
                password=LEARNER_EMAIL,
                site=site,
            ),
        )
        created = True

    EmailAddress.objects.update_or_create(
        user=learner,
        email=learner.email,
        defaults={"verified": True, "primary": True},
    )
    return learner, created


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
                "Dedicated course for QA of free-text answers in a non-scored "
                "(questionnaire/survey) form."
            ),
            site=site,
        ),
    )


def _build_survey(site: Site) -> Form:
    """CATEGORY_VALUE_SUM form built only from free-text questions. Idempotent."""
    existing: Form | None = Form.objects.filter(slug=FORM_SLUG, site=site).first()
    if existing is not None:
        return existing

    form = cast(
        Form,
        FormFactory(
            title=FORM_TITLE,
            slug=FORM_SLUG,
            strategy=FormStrategy.CATEGORY_VALUE_SUM,
            quiz_show_incorrect=None,
            quiz_pass_percentage=None,
            site=site,
        ),
    )

    for page_order, (page_title, page_slug, questions) in enumerate(SURVEY_PAGES):
        page = cast(
            FormPage,
            FormPageFactory(
                form=form,
                title=page_title,
                slug=page_slug,
                order=page_order,
                category=PAGE_CATEGORY,
                site=site,
            ),
        )
        for order, (text, question_type, required) in enumerate(questions):
            FormQuestionFactory(
                form_page=page,
                question=text,
                type=question_type,
                required=required,
                order=order,
                site=site,
            )

    return form


def _attach_to_course(course: Course, form: Form, site: Site) -> None:
    already = any(item.child_id == form.pk for item in course.items.all())
    if not already:
        ContentCollectionItemFactory(
            collection_object=course, child_object=form, order=0, site=site
        )


def _register(learner: User, course: Course, site: Site) -> None:
    if not LearnerCourseRegistration.objects.filter(
        learner__user=learner, collection=course, site=site
    ).exists():
        LearnerCourseRegistrationFactory(
            learner__user=learner,
            learner__organisation=get_default_organisation(site),
            collection=course,
            site=site,
        )


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
    """Seed a non-scored survey with free-text questions, and its QA learner."""
    site = _get_site(site_name)
    learner, created = _get_or_create_learner(site)
    course = _get_or_create_course(site)
    form = _build_survey(site)
    _attach_to_course(course, form, site)
    _register(learner, course, site)
    index = _item_index(course, form)

    click.secho(
        "\n--- Free-text in a non-scored form (QA 12.4) ---", fg="cyan", bold=True
    )
    click.secho(f"Site:   {site.name} ({site.domain}) [id {site.pk}]", fg="cyan")
    click.secho(
        f"{'Created' if created else 'Reused'} learner login: "
        f"{learner.email} / {learner.email}",
        fg="green",
        bold=True,
    )
    click.secho(f"Course: {course.title}  [slug: {course.slug}]", fg="cyan")
    click.secho(
        f"Form:   {form.title}  [slug: {form.slug}, strategy: {form.strategy}]",
        fg="cyan",
    )
    click.echo(f"  quiz_pass_percentage: {form.quiz_pass_percentage}")
    click.echo(f"  quiz_show_incorrect : {form.quiz_show_incorrect}")
    click.secho(
        f"Start screen : /courses/{course.slug}/{index}/", fg="green", bold=True
    )
    click.secho(
        f"Runner page 1: /courses/{course.slug}/{index}/fill_form/1", fg="green"
    )
    click.secho(
        f"Runner page 2: /courses/{course.slug}/{index}/fill_form/2", fg="green"
    )
    click.secho(f"Results page : /courses/{course.slug}/{index}/complete", fg="green")

    click.secho("\nQuestions:", fg="cyan", bold=True)
    for question in (
        FormQuestion.objects.filter(form_page__form=form)
        .select_related("form_page")
        .order_by("form_page__order", "order")
    ):
        flag = "required" if question.required else "optional"
        click.echo(
            f"  p{question.form_page.order + 1} [{question.type}, {flag}] "
            f"{question.question}"
        )
