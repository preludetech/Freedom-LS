"""Create a QUIZ form exercising all four question types, on a dedicated course.

Builds (idempotently) a single-item course whose only viewable item is a QUIZ
Form. The form has one FormPage with exactly one question of each supported
type, in order:

1. multiple_choice (single-select radio) - 3 options, one correct, required
2. checkboxes (multi-select)            - 3 options, two correct, required
3. short_text (<input type="text">)     - required
4. long_text (<textarea>)               - required

The form is attached as a course content item and the learner
``demodev@email.com`` is registered for the course, so the start screen is
reachable at ``/courses/<course-slug>/1/`` and the runner at
``/courses/<course-slug>/1/fill_form/<page_number>``.

The login convention in this project is password == email address.
"""

from typing import cast

import djclick as click
from allauth.account.models import EmailAddress

from django.contrib.sites.models import Site

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
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
    QuestionOption,
    QuestionType,
)
from freedom_ls.student_management.factories import UserCourseRegistrationFactory
from freedom_ls.student_management.models import UserCourseRegistration

LEARNER_EMAIL = "demodev@email.com"

COURSE_TITLE = "QA Question Types Course"
COURSE_SLUG = "qa-question-types-course"

FORM_TITLE = "QA All Question Types Form"
FORM_SLUG = "qa-all-question-types-form"

PAGE_TITLE = "QA Question Types Page"
PAGE_SLUG = "qa-question-types-page"

MC_QUESTION = "MC question"
CHECKBOX_QUESTION = "Checkbox question"
SHORT_TEXT_QUESTION = "Short text question"
LONG_TEXT_QUESTION = "Long text question"


def _get_site(site_name: str) -> Site:
    try:
        return Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e


def _get_learner(site: Site) -> User:
    """Fetch the existing demodev learner, ensuring it can log in."""
    learner: User | None = User.objects.filter(email=LEARNER_EMAIL, site=site).first()
    if learner is None:
        raise click.ClickException(
            f"Learner '{LEARNER_EMAIL}' not found on site '{site.name}'."
        )
    learner.is_active = True
    learner.set_password(LEARNER_EMAIL)
    learner.save(update_fields=["is_active", "password"])
    EmailAddress.objects.update_or_create(
        user=learner,
        email=learner.email,
        defaults={"verified": True, "primary": True},
    )
    return learner


def _get_or_create_course(site: Site) -> Course:
    existing: Course | None = Course.objects.filter(slug=COURSE_SLUG, site=site).first()
    if existing is not None:
        return existing
    return cast(
        Course,
        CourseFactory(
            title=COURSE_TITLE,
            slug=COURSE_SLUG,
            description="Dedicated course for QA of the four form question types.",
            site=site,
        ),
    )


def _build_form(site: Site) -> Form:
    """Create the QUIZ form with one page and one question of each type.

    Idempotent: if the form already exists it is returned untouched (its page,
    questions and options are assumed to already be present from a prior run).
    """
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
            quiz_pass_percentage=50,
            site=site,
        ),
    )

    page = cast(
        FormPage,
        FormPageFactory(
            form=form,
            title=PAGE_TITLE,
            slug=PAGE_SLUG,
            order=0,
            site=site,
        ),
    )

    # 1. multiple_choice - 3 options, exactly one correct.
    mc = cast(
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
    for i, (text, correct) in enumerate(
        [("MC option A", True), ("MC option B", False), ("MC option C", False)]
    ):
        QuestionOptionFactory(
            question=mc,
            text=text,
            value=str(i + 1),
            order=i,
            correct=correct,
            site=site,
        )

    # 2. checkboxes - 3 options, two correct.
    cb = cast(
        FormQuestion,
        FormQuestionFactory(
            form_page=page,
            question=CHECKBOX_QUESTION,
            type=QuestionType.CHECKBOXES,
            required=True,
            order=1,
            site=site,
        ),
    )
    for i, (text, correct) in enumerate(
        [
            ("Checkbox option A", True),
            ("Checkbox option B", True),
            ("Checkbox option C", False),
        ]
    ):
        QuestionOptionFactory(
            question=cb,
            text=text,
            value=str(i + 1),
            order=i,
            correct=correct,
            site=site,
        )

    # 3. short_text - no options.
    FormQuestionFactory(
        form_page=page,
        question=SHORT_TEXT_QUESTION,
        type=QuestionType.SHORT_TEXT,
        required=True,
        order=2,
        site=site,
    )

    # 4. long_text - no options.
    FormQuestionFactory(
        form_page=page,
        question=LONG_TEXT_QUESTION,
        type=QuestionType.LONG_TEXT,
        required=True,
        order=3,
        site=site,
    )

    return form


def _attach_form_to_course(course: Course, form: Form, site: Site) -> None:
    """Attach the form as the course's only content item (idempotent)."""
    already = any(item.child_id == form.pk for item in course.items.all())
    if not already:
        ContentCollectionItemFactory(
            collection_object=course, child_object=form, order=0, site=site
        )


def _register(learner: User, course: Course, site: Site) -> None:
    if not UserCourseRegistration.objects.filter(
        user=learner, collection=course, site=site
    ).exists():
        UserCourseRegistrationFactory(user=learner, collection=course, site=site)


@click.command()
@click.argument("site_name", default="DemoDev")
def command(site_name: str) -> None:
    """Create a QUIZ form with all four question types on a dedicated course.

    SITE_NAME is the site to create data on (default: DemoDev).
    """
    site = _get_site(site_name)
    learner = _get_learner(site)
    course = _get_or_create_course(site)
    form = _build_form(site)
    _attach_form_to_course(course, form, site)
    _register(learner, course, site)

    # Resolve the 1-based index of the form within the course's viewable items.
    viewable = course.viewable_items()
    index = next((i + 1 for i, item in enumerate(viewable) if item.pk == form.pk), None)
    if index is None:
        raise click.ClickException(
            "Form was not found in the course's viewable items after attaching."
        )

    questions = list(
        FormQuestion.objects.filter(form_page__form=form).order_by("order")
    )
    option_count = QuestionOption.objects.filter(question__form_page__form=form).count()

    click.secho("\n--- Summary ---", fg="cyan", bold=True)
    click.secho(f"Site:    {site.name} ({site.domain})", fg="cyan")
    click.secho(
        f"Login:   {learner.email} / {learner.email} (verified, active)",
        fg="cyan",
        bold=True,
    )
    click.secho(f"Course:  {course.title}  [slug: {course.slug}]", fg="cyan")
    click.secho(
        f"Form:    {form.title}  [strategy: {form.strategy}, item index: {index}]",
        fg="cyan",
    )
    click.secho(f"Start screen: /courses/{course.slug}/{index}/", fg="green", bold=True)
    click.secho(
        f"Runner page 1: /courses/{course.slug}/{index}/fill_form/1",
        fg="green",
    )
    click.secho(
        f"Questions ({len(questions)}), {option_count} options total:", fg="cyan"
    )
    for q in questions:
        click.secho(f"  - [{q.type}] {q.question}", fg="cyan")
