"""Seed the two phone-question QA fixtures.

1. "QA Phone Course" (``qa-phone-course``): a single-item course whose only
   item is the unscored form "QA Phone Form", one page, two questions:
   a required ``phone`` question "Contact number" and an optional
   ``short_text`` question "Anything else". ``demodev@email.com`` is
   registered on it.

2. A legacy phone answer: a verified learner (default
   ``qa-legacy@email.com``, password == email) holding an UNSUBMITTED
   application on the application-gated demo course, whose sitting stores the
   pre-E.164 text ``082 123 4567`` for "What is your phone number?", written
   straight to ``QuestionAnswer`` rather than through the form. Every other
   required question on the application form's first page is answered too.

Idempotent: re-running reuses the course, form, application and sitting,
re-opens a sitting that was submitted, and rewrites the seeded answers. It
deletes nothing.

Usage:
    uv run python manage.py qa_create_phone_question_scenario
    uv run python manage.py qa_create_phone_question_scenario \
        --legacy-email qa-legacy@email.com --site-name DemoDev
"""

from typing import cast

import djclick as click

from django.contrib.sites.models import Site
from django.db import transaction

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
)
from freedom_ls.form_engine.models import (
    Form,
    FormPage,
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionAnswer,
    QuestionType,
)
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.qa_helpers.management.commands.qa_create_clean_applicant import (
    _ensure_user,
    _ensure_verified_email,
)
from freedom_ls.qa_helpers.management.commands.qa_create_form_question_types import (
    _attach_form_to_course,
    _get_learner,
    _get_site,
    _register,
)

COURSE_TITLE = "QA Phone Course"
COURSE_SLUG = "qa-phone-course"
FORM_TITLE = "QA Phone Form"
FORM_SLUG = "qa-phone-form"
PAGE_TITLE = "Your contact details"
PHONE_QUESTION = "Contact number"
EXTRA_QUESTION = "Anything else"

GATED_COURSE_SLUG = "functionality-demo-application-gated-course"
LEGACY_PHONE_QUESTION = "What is your phone number?"
LEGACY_PHONE_TEXT = "082 123 4567"

# Required questions on page 1 ("About you") of the demo application form.
# Free-text answers by question text; choice answers by option value.
PAGE_ONE_TEXT_ANSWERS = {
    "What is your full name?": "Quinn Legacy",
    "What is your date of birth?": "1990-05-15",
    "What is your email address?": "",  # filled with the persona's email
    "How many years have you been writing software?": "4",
}
PAGE_ONE_CHOICE_ANSWERS = {
    "How did you hear about this course?": "word_of_mouth",
    "Is your employer paying for this course?": "no",
}


def _get_or_create_course(site: Site) -> Course:
    existing = Course._base_manager.filter(slug=COURSE_SLUG, site=site).first()
    if existing is not None:
        return existing
    return cast(
        Course,
        CourseFactory(
            title=COURSE_TITLE,
            slug=COURSE_SLUG,
            description="Dedicated course for QA of the phone question type.",
            site=site,
        ),
    )


def _get_or_create_phone_form(site: Site) -> Form:
    existing = Form._base_manager.filter(slug=FORM_SLUG, site=site).first()
    if existing is not None:
        return existing
    form = cast(
        Form,
        FormFactory(
            title=FORM_TITLE,
            slug=FORM_SLUG,
            strategy=FormStrategy.UNSCORED,
            site=site,
        ),
    )
    page = cast(
        FormPage,
        FormPageFactory(form=form, title=PAGE_TITLE, order=0, site=site),
    )
    FormQuestionFactory(
        form_page=page,
        question=PHONE_QUESTION,
        type=QuestionType.PHONE,
        required=True,
        order=0,
        site=site,
    )
    FormQuestionFactory(
        form_page=page,
        question=EXTRA_QUESTION,
        type=QuestionType.SHORT_TEXT,
        required=False,
        order=1,
        site=site,
    )
    return form


def _page_one_question(page: FormPage, text: str) -> FormQuestion:
    question = FormQuestion._base_manager.filter(form_page=page, question=text).first()
    if question is None:
        raise click.ClickException(
            f"Question {text!r} not found on page {page.title!r}."
        )
    return question


def _seed_legacy_sitting(
    user: User, site: Site
) -> tuple[CourseApplication, FormProgress, dict[str, QuestionAnswer]]:
    course = Course._base_manager.filter(site=site, slug=GATED_COURSE_SLUG).first()
    if course is None or course.application_form is None:
        raise click.ClickException(
            f"Course {GATED_COURSE_SLUG!r} with an application form is missing; "
            "run content_save demo_content DemoDev first."
        )
    form = course.application_form
    page = FormPage._base_manager.filter(form=form).order_by("order").first()
    if page is None:
        raise click.ClickException(f"Form {form.title!r} has no pages.")

    application = CourseApplication._base_manager.filter(
        site=site, user=user, course=course
    ).first()
    if application is None:
        application = cast(
            CourseApplication,
            CourseApplicationFactory(user=user, course=course, site=site),
        )
    sitting = application.form_progress
    if sitting is None:
        sitting = cast(
            FormProgress, FormProgressFactory(user=user, form=form, site=site)
        )
        application.form_progress = sitting
        application.save(update_fields=["form_progress"])
    # Unsubmitted, shown page 1 so the runner resumes there.
    FormProgress._base_manager.filter(pk=sitting.pk).update(
        completed_time=None, scores=None, asked=None, furthest_page_reached=1
    )
    sitting.refresh_from_db()

    answers: dict[str, QuestionAnswer] = {}

    def _answer(text: str) -> QuestionAnswer:
        question = _page_one_question(page, text)
        answer, _ = QuestionAnswer._base_manager.get_or_create(
            form_progress=sitting, question=question, site=site
        )
        answers[text] = answer
        return answer

    for text, value in PAGE_ONE_TEXT_ANSWERS.items():
        answer = _answer(text)
        answer.text_answer = value or user.email
        answer.save()
    for text, option_value in PAGE_ONE_CHOICE_ANSWERS.items():
        answer = _answer(text)
        option = answer.question.options.filter(value=option_value).first()
        if option is None:
            raise click.ClickException(f"Option {option_value!r} missing on {text!r}.")
        answer.selected_options.set([option])

    # The legacy value, written directly so no E.164 normalisation runs.
    phone = _answer(LEGACY_PHONE_QUESTION)
    QuestionAnswer._base_manager.filter(pk=phone.pk).update(
        text_answer=LEGACY_PHONE_TEXT
    )
    phone.refresh_from_db()
    return application, sitting, answers


@click.command()
@click.option(
    "--legacy-email",
    default="qa-legacy@email.com",
    help="Learner holding the legacy phone answer (default qa-legacy@email.com).",
)
@click.option("--site-name", default="DemoDev", help="Site name (default DemoDev).")
def command(legacy_email: str, site_name: str) -> None:
    """Seed the QA Phone Course and a legacy (pre-E.164) phone answer."""
    site = _get_site(site_name)
    with transaction.atomic():
        admin = _get_learner(site)
        course = _get_or_create_course(site)
        form = _get_or_create_phone_form(site)
        _attach_form_to_course(course, form, site)
        _register(admin, course, site)

        legacy_user, created = _ensure_user(legacy_email, site)
        _ensure_verified_email(legacy_user)
        LearnerFactory(
            user=legacy_user, organisation=get_default_organisation(site), site=site
        )
        application, sitting, answers = _seed_legacy_sitting(legacy_user, site)

    index = next(
        i + 1 for i, item in enumerate(course.viewable_items()) if item.pk == form.pk
    )
    click.secho("\n--- QA Phone Course ---", fg="cyan", bold=True)
    click.echo(f"Course: {course.title} [slug {course.slug}, pk {course.pk}]")
    click.echo(f"Form:   {form.title} [slug {form.slug}, pk {form.pk}]")
    for q in FormQuestion._base_manager.filter(form_page__form=form).order_by("order"):
        click.echo(f"  - [{q.type}] {q.question} required={q.required} pk={q.pk}")
    click.echo(f"Registered: {admin.email}")
    click.echo(f"Start screen: /courses/{course.slug}/{index}/")
    click.echo(f"Runner page 1: /courses/{course.slug}/{index}/fill_form/1")

    click.secho("\n--- Legacy phone answer ---", fg="cyan", bold=True)
    click.echo(
        f"User: {legacy_user.email} pk={legacy_user.pk} "
        f"({'created' if created else 'reset'}; password == email)"
    )
    click.echo(f"CourseApplication pk={application.pk}")
    click.echo(
        f"FormProgress pk={sitting.pk} completed_time={sitting.completed_time} "
        f"furthest_page_reached={sitting.furthest_page_reached}"
    )
    for text, answer in answers.items():
        answer.refresh_from_db()
        stored = answer.text_answer or [o.value for o in answer.selected_options.all()]
        click.echo(f"  QuestionAnswer pk={answer.pk} {text!r} -> {stored!r}")
    click.echo(f"Form page 1: /applications/application/{application.pk}/page/1/")
