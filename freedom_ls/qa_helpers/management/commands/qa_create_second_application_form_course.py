"""Create a second application-gated course with its own form, for export QA.

Creates (idempotently) on a single site (default: DemoDev):

1. A gated course "QA Second Course" whose access_config names an application
   form and whose `application_form` FK points at it (the way the content
   loader binds the demo gated course).
2. That form, "Second form": one page, two short-text questions in order:
   "What is your full name?" (same text as the demo Application form's first
   question, on purpose) and "Favourite colour".
3. A submitted CourseApplication by the existing user qa_applicant@email.com,
   whose completed sitting answers "Ada Again" and "Teal".

The applicant user is only read, never modified. Nothing else is touched.
"""

from typing import cast

import djclick as click

from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course, CourseCategory
from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.form_engine.enums import QuestionType
from freedom_ls.form_engine.exports import answer_cell
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
)
from freedom_ls.form_engine.models import (
    Form,
    FormPage,
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionAnswer,
)

APPLICANT_EMAIL = "qa_applicant@email.com"
COURSE_TITLE = "QA Second Course"
COURSE_SLUG = "qa-second-course"
FORM_TITLE = "Second form"
FORM_SLUG = "second-form"
PAGE_TITLE = "About you"
PAGE_SLUG = "qa-second-form-about-you"
# (order, question text, answer text), in page order.
QUESTIONS = [
    (1, "What is your full name?", "Ada Again"),
    (2, "Favourite colour", "Teal"),
]


def _get_or_create_form(site: Site) -> tuple[Form, list[FormQuestion]]:
    form: Form | None = Form.objects.filter(slug=FORM_SLUG, site=site).first()
    if form is None:
        form = cast(
            Form,
            FormFactory(
                title=FORM_TITLE,
                slug=FORM_SLUG,
                strategy=FormStrategy.UNSCORED,
                site=site,
            ),
        )
    page: FormPage | None = FormPage.objects.filter(form=form, site=site).first()
    if page is None:
        page = cast(
            FormPage,
            FormPageFactory(
                form=form, title=PAGE_TITLE, slug=PAGE_SLUG, order=1, site=site
            ),
        )
    questions: list[FormQuestion] = []
    for order, text, _answer in QUESTIONS:
        question: FormQuestion | None = FormQuestion.objects.filter(
            form_page=page, question=text, site=site
        ).first()
        if question is None:
            question = cast(
                FormQuestion,
                FormQuestionFactory(
                    form_page=page,
                    question=text,
                    type=QuestionType.SHORT_TEXT,
                    order=order,
                    required=True,
                    site=site,
                ),
            )
        questions.append(question)
    return form, questions


def _get_or_create_course(site: Site, form: Form) -> Course:
    category, _ = CourseCategory.objects.get_or_create(
        site=site,
        slug="product-analytics",
        defaults={"title": "Product Analytics", "file_path": ""},
    )
    fields = {
        "title": COURSE_TITLE,
        "description": "A second application-gated course for export QA.",
        "access_config": {
            "access_type": "application_gated",
            "application_form": "../qa_second_form/form.md",
        },
        "application_form": form,
        "dashboard_category": category,
    }
    course: Course | None = Course.objects.filter(slug=COURSE_SLUG, site=site).first()
    if course is None:
        course = cast(Course, CourseFactory(slug=COURSE_SLUG, site=site, **fields))
    else:
        for name, value in fields.items():
            setattr(course, name, value)
        course.save(update_fields=list(fields.keys()))
    course.categories.set([category])
    return course


def _get_or_create_application(
    site: Site, user: User, course: Course, form: Form, questions: list[FormQuestion]
) -> CourseApplication:
    application: CourseApplication | None = (
        CourseApplication.objects.filter(user=user, course=course, site=site)
        .select_related("form_progress")
        .first()
    )
    if application is None:
        new_sitting = cast(
            FormProgress,
            FormProgressFactory(
                user=user,
                form=form,
                completed_time=timezone.now(),
                furthest_page_reached=1,
                site=site,
            ),
        )
        application = cast(
            CourseApplication,
            CourseApplicationFactory(
                user=user, course=course, form_progress=new_sitting, site=site
            ),
        )
    sitting = application.form_progress
    if sitting is None:
        raise click.ClickException(
            f"Application {application.pk} has no form sitting; reset it first."
        )
    if sitting.completed_time is None:
        sitting.completed_time = timezone.now()
        sitting.save(update_fields=["completed_time"])
    for question, (_order, _text, answer_text) in zip(
        questions, QUESTIONS, strict=True
    ):
        answer: QuestionAnswer | None = QuestionAnswer.objects.filter(
            form_progress=sitting, question=question
        ).first()
        if answer is None:
            QuestionAnswerFactory(
                form_progress=sitting,
                question=question,
                text_answer=answer_text,
                site=site,
            )
        elif answer.text_answer != answer_text:
            answer.text_answer = answer_text
            answer.save(update_fields=["text_answer"])
    return cast(
        CourseApplication,
        CourseApplication.objects.select_related("form_progress").get(
            pk=application.pk
        ),
    )


@click.command()
@click.argument("site_name", default="DemoDev")
def command(site_name: str) -> None:
    """Create the second gated course, its form and a submitted application.

    SITE_NAME is the site to create data on (default: DemoDev).
    """
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e
    user: User | None = User.objects.filter(email=APPLICANT_EMAIL).first()
    if user is None:
        raise click.ClickException(f"User {APPLICANT_EMAIL} does not exist.")

    form, questions = _get_or_create_form(site)
    course = _get_or_create_course(site, form)
    application = _get_or_create_application(site, user, course, form, questions)

    click.secho(f"Site: {site.name} ({site.domain})", fg="cyan")
    click.secho(
        f"Course: {course.pk}  '{course.title}'  slug={course.slug}", fg="green"
    )
    click.secho(f"  access_config={course.access_config}", fg="green")
    click.secho(f"  application_form_id={course.application_form_id}", fg="green")
    click.secho(f"Form: {form.pk}  '{form.title}'", fg="green")
    ordered = FormQuestion.objects.filter(form_page__form=form).order_by(
        "form_page__order", "order"
    )
    for question in ordered:
        click.secho(
            f"  Question {question.order}: {question.pk}  '{question.question}'"
        )
    click.secho(
        f"Application: {application.pk}  is_submitted={application.is_submitted}  "
        f"submitted_time={application.submitted_time}",
        fg="green",
    )
    answers = QuestionAnswer.objects.filter(
        form_progress=application.form_progress
    ).select_related("question")
    by_question = {answer.question_id: answer for answer in answers}
    for question in ordered:
        click.secho(
            f"  Answer to '{question.question}': {answer_cell(by_question.get(question.pk))!r}"
        )
