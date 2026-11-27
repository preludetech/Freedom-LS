"""Seed the browser-QA scenario for immutable question versions pinned per sitting.

Creates, on one site (default: DemoDev):

1. "QA Versioned Course", placing in order:

   1. "QA Versioned Quiz" - QUIZ, pass mark 50, incorrect answers shown. One
      page: Q1 "What is the reserve fuel for a VFR day flight?" (30 minutes
      correct) and Q2 "Which colour is the left navigation light?" (Red
      correct). Both get version 1. Then:

      - S1: ``versions-learner@email.com`` answers Q1 "45 minutes" (wrong) and
        Q2 "Red" (right) and completes it: score 1/2.
      - S2: ``versions-learner-2@email.com`` starts it (served paper written,
        page 1 reached, no answers) and leaves it open.
      - Q1 is revised to version 2: "What is the minimum reserve fuel for a VFR
        day flight?", with "45 minutes" correct instead of "30 minutes".

   2. "QA Versioned Survey" - UNSCORED, one question "How did you hear about
      us?" (Friend, Advert), version 1. ``versions-learner@email.com`` answers
      "Friend" and completes it; then the question is revised to "How did you
      first hear about us?" (version 2).

   ``versions-learner-3@email.com`` is registered on the course with no
   sitting, so a tester can take the quiz for the first time (it allows no
   retake after a pass).

2. "QA Versioned Application Course", application-gated on "QA Versioned
   Application Form": one short-text question "Your licence number" (version
   1). ``versions-applicant@email.com`` holds a draft application whose sitting
   answers it, so check-your-answers is ready to submit; then the question is
   revised to "Your pilot licence number" (version 2).

Every version is written by ``save_question_version``. Every sitting goes
through the product's own code: ``get_or_create_incomplete`` or
``_start_application`` to begin it, ``ensure_served_paper`` to serve it,
``save_answers`` on the served page's questions (which pins each answer to its
version) and ``complete()`` to score it. Passwords equal the email address.

Each of the three parts is built in one transaction, and only when its form
does not exist yet, so a re-run creates nothing twice and only reports.

Usage:
    uv run python manage.py qa_create_question_versions_scenario
    uv run python manage.py qa_create_question_versions_scenario --site-name DemoDev
"""

from typing import cast

import djclick as click

from django.contrib.sites.models import Site
from django.db import transaction
from django.http import QueryDict
from django.urls import reverse

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.course_applications.models import ACTIVE_STATES, CourseApplication
from freedom_ls.course_applications.views import _start_application
from freedom_ls.form_engine.conditions import current_path
from freedom_ls.form_engine.models import (
    Form,
    FormProgress,
    FormQuestion,
    FormQuestionVersion,
    FormStrategy,
    QuestionType,
    save_question_version,
)
from freedom_ls.form_engine.page_flow import resolve_page
from freedom_ls.form_engine.served_paper import ensure_served_paper
from freedom_ls.learner_progress.attempts import get_or_create_incomplete
from freedom_ls.qa_helpers.management.commands.qa_create_attempt_review_scenario import (
    FormSpec,
    OptionSpec,
    PageSpec,
    QuestionSpec,
    _create_form,
    _file_path,
    _place_forms,
)
from freedom_ls.qa_helpers.management.commands.qa_create_multiselect_quiz_scoring import (
    _collection_item_for,
    _get_or_create_user,
    _get_site,
    _item_index,
    _record_for,
    _register,
)
from freedom_ls.qa_helpers.management.commands.qa_create_organisation_scenarios import (
    _pin_current_site,
    _site_context,
)

FILE_PATH_ROOT = "qa/question_versions"
LEARNER_EMAIL = "versions-learner@email.com"
LEARNER_2_EMAIL = "versions-learner-2@email.com"
LEARNER_3_EMAIL = "versions-learner-3@email.com"
APPLICANT_EMAIL = "versions-applicant@email.com"

COURSE_TITLE = "QA Versioned Course"
COURSE_SLUG = "qa-versioned-course"
APPLICATION_COURSE_TITLE = "QA Versioned Application Course"
APPLICATION_COURSE_SLUG = "qa-versioned-application-course"

QUIZ = FormSpec(
    title="QA Versioned Quiz",
    slug="qa-versioned-quiz",
    strategy=FormStrategy.QUIZ,
    quiz_pass_percentage=50,
    file_path_root=FILE_PATH_ROOT,
    pages=(
        PageSpec(
            title="Fuel and lights",
            questions=(
                QuestionSpec(
                    "q1",
                    "What is the reserve fuel for a VFR day flight?",
                    QuestionType.MULTIPLE_CHOICE,
                    (
                        OptionSpec("30 minutes", True),
                        OptionSpec("45 minutes"),
                        OptionSpec("10 minutes"),
                    ),
                ),
                QuestionSpec(
                    "q2",
                    "Which colour is the left navigation light?",
                    QuestionType.MULTIPLE_CHOICE,
                    (OptionSpec("Red", True), OptionSpec("Green")),
                ),
            ),
        ),
    ),
)
QUIZ_Q1_REVISED = "What is the minimum reserve fuel for a VFR day flight?"
QUIZ_Q1_REVISED_CORRECT = "45 minutes"
S1_ANSWERS = {"q1": "45 minutes", "q2": "Red"}

SURVEY = FormSpec(
    title="QA Versioned Survey",
    slug="qa-versioned-survey",
    strategy=FormStrategy.UNSCORED,
    file_path_root=FILE_PATH_ROOT,
    pages=(
        PageSpec(
            title="About you",
            questions=(
                QuestionSpec(
                    "s1",
                    "How did you hear about us?",
                    QuestionType.MULTIPLE_CHOICE,
                    (OptionSpec("Friend"), OptionSpec("Advert")),
                ),
            ),
        ),
    ),
)
SURVEY_REVISED = "How did you first hear about us?"
SURVEY_ANSWERS = {"s1": "Friend"}

APPLICATION_FORM = FormSpec(
    title="QA Versioned Application Form",
    slug="qa-versioned-application-form",
    strategy=FormStrategy.UNSCORED,
    file_path_root=FILE_PATH_ROOT,
    pages=(
        PageSpec(
            title="Your licence",
            questions=(
                QuestionSpec("a1", "Your licence number", QuestionType.SHORT_TEXT),
            ),
        ),
    ),
)
APPLICATION_REVISED = "Your pilot licence number"
APPLICATION_ANSWER = "ZA-PPL-123456"

ADMIN_FORM_PROGRESS_URL = "admin:freedom_ls_form_engine_formprogress_change"


def _questions(form: Form) -> list[FormQuestion]:
    """The form's questions in authored order."""
    return list(
        FormQuestion.objects.filter(form_page__form=form)
        .select_related("form_page")
        .order_by("form_page__order", "order")
    )


def _save_versions(questions: list[FormQuestion]) -> None:
    for question in questions:
        saved = save_question_version(question, list(question.options.all()), "")
        number = saved.version.number if saved.version else saved.previous_number
        click.echo(f"  Version {number} of '{question.question}'")


def _revise(
    question: FormQuestion, wording: str, correct_option: str | None = None
) -> None:
    """Change the live question, then save the change as its next version."""
    question.question = wording
    question.save(update_fields=["question"])
    if correct_option is not None:
        for option in question.options.all():
            option.correct = option.text == correct_option
            option.save(update_fields=["correct"])
    _save_versions([question])


def _post_data(
    sitting: FormProgress, questions: list[FormQuestion], answers: dict[str, str]
) -> QueryDict:
    """The POST a learner sends for page 1: each slot's option by text, or typed text."""
    by_slot = dict(
        zip((spec.slot for spec in _specs_of(sitting.form)), questions, strict=True)
    )
    post_data = QueryDict(mutable=True)
    for slot, value in answers.items():
        question = by_slot[slot]
        if question.type == QuestionType.SHORT_TEXT:
            post_data[f"question_{question.id}"] = value
        else:
            post_data[f"question_{question.id}"] = str(
                question.options.get(text=value).pk
            )
    return post_data


def _specs_of(form: Form) -> list[QuestionSpec]:
    spec = {s.slug: s for s in (QUIZ, SURVEY, APPLICATION_FORM)}[form.slug]
    return [q for page in spec.pages for q in page.questions]


def _answer_page_one(sitting: FormProgress, answers: dict[str, str]) -> None:
    """Serve the sitting, show it page 1 and save `answers` there, as the page view does."""
    ensure_served_paper(sitting)
    path = current_path(sitting)
    current = resolve_page(path, 1)
    sitting.record_page_reached(1, path)
    if not answers:
        return
    rejected = sitting.save_answers(
        current.questions, _post_data(sitting, _questions(sitting.form), answers)
    )
    if rejected:
        raise click.ClickException(f"Answers rejected: {list(rejected)}")


def _sit(
    user: User, course: Course, form: Form, answers: dict[str, str], *, complete: bool
) -> FormProgress:
    record = _record_for(user, course)
    sitting = get_or_create_incomplete(record, _collection_item_for(course, form))
    _answer_page_one(sitting, answers)
    if complete:
        sitting.complete()
    sitting.refresh_from_db()
    return sitting


def _get_or_create_course(
    site: Site, slug: str, title: str, **fields: object
) -> Course:
    existing: Course | None = Course.objects.filter(slug=slug, site=site).first()
    if existing is not None:
        return existing
    return cast(
        Course,
        CourseFactory(
            title=title,
            slug=slug,
            description="QA course for question versions pinned per sitting.",
            file_path=_file_path("courses", f"{slug}.md", root=FILE_PATH_ROOT),
            site=site,
            **fields,
        ),
    )


def _place(course: Course, forms: list[Form], site: Site) -> Course:
    """Place the forms, and return the course re-read: its item tree is memoized
    per instance, so the instance passed in does not see the new placements."""
    _place_forms(course, forms, site)
    return cast(Course, Course.objects.get(pk=course.pk))


def _existing_form(site: Site, spec: FormSpec) -> Form | None:
    return Form.objects.filter(slug=spec.slug, site=site).first()


def _seed_quiz(site: Site, course: Course, learner: User, learner_2: User) -> None:
    if _existing_form(site, QUIZ) is not None:
        click.echo(f"'{QUIZ.title}' exists; left as it is.")
        return
    click.secho(f"Creating '{QUIZ.title}'", fg="green")
    with transaction.atomic():
        quiz = _create_form(QUIZ, site)
        course = _place(course, [quiz], site)
        q1, q2 = _questions(quiz)
        _save_versions([q1, q2])
        s1 = _sit(learner, course, quiz, S1_ANSWERS, complete=True)
        if s1.scores is None or (s1.scores["score"], s1.scores["max_score"]) != (1, 2):
            raise click.ClickException(f"S1 scored {s1.scores}, expected 1/2.")
        _sit(learner_2, course, quiz, {}, complete=False)
        _revise(q1, QUIZ_Q1_REVISED, QUIZ_Q1_REVISED_CORRECT)


def _seed_survey(site: Site, course: Course, learner: User) -> None:
    if _existing_form(site, SURVEY) is not None:
        click.echo(f"'{SURVEY.title}' exists; left as it is.")
        return
    click.secho(f"Creating '{SURVEY.title}'", fg="green")
    with transaction.atomic():
        survey = _create_form(SURVEY, site)
        quiz = _existing_form(site, QUIZ)
        course = _place(course, [quiz, survey] if quiz else [survey], site)
        (question,) = _questions(survey)
        _save_versions([question])
        _sit(learner, course, survey, SURVEY_ANSWERS, complete=True)
        _revise(question, SURVEY_REVISED)


def _seed_application(site: Site, applicant: User) -> None:
    if _existing_form(site, APPLICATION_FORM) is not None:
        click.echo(f"'{APPLICATION_FORM.title}' exists; left as it is.")
        return
    click.secho(f"Creating '{APPLICATION_FORM.title}'", fg="green")
    with transaction.atomic():
        form = _create_form(APPLICATION_FORM, site)
        course = _get_or_create_course(
            site,
            APPLICATION_COURSE_SLUG,
            APPLICATION_COURSE_TITLE,
            access_config={
                "access_type": "application_gated",
                "application_form": f"../{APPLICATION_FORM.slug}/form.md",
            },
            application_form=form,
        )
        (question,) = _questions(form)
        _save_versions([question])
        application, _created = _start_application(course, user=applicant)
        if application.form_progress is None:
            raise click.ClickException(f"Application {application.pk} has no sitting.")
        _answer_page_one(application.form_progress, {"a1": APPLICATION_ANSWER})
        _revise(question, APPLICATION_REVISED)


def _sittings(user: User, form: Form) -> list[FormProgress]:
    return list(
        FormProgress.objects.filter(user=user, form=form)
        .prefetch_related("answers__question_version", "answers__selected_options")
        .order_by("start_time")
    )


def _describe(label: str, sitting: FormProgress) -> None:
    state = "completed" if sitting.completed_time else "IN PROGRESS"
    click.secho(f"  {label}: FormProgress {sitting.pk} ({state})", fg="cyan")
    click.echo(f"    scores={sitting.scores}")
    click.echo(
        "    admin: "
        + reverse(ADMIN_FORM_PROGRESS_URL, kwargs={"object_id": sitting.pk})
    )
    for answer in sitting.answers.all():
        given = answer.text_answer or ", ".join(
            o.text for o in answer.selected_options.all()
        )
        version = answer.question_version
        click.echo(
            f"    answer '{given}' pinned to v{version.number if version else '-'}"
            f" ('{version.question_text if version else ''}')"
        )


def _report_versions(form: Form) -> None:
    for question in _questions(form):
        versions = FormQuestionVersion.unfiltered.filter(question=question).order_by(
            "number"
        )
        click.echo(f"  Live: '{question.question}'")
        for version in versions:
            correct = [o.text for o in version.option_rows() if o.correct]
            click.echo(
                f"    v{version.number} {version.pk}: '{version.question_text}'"
                f" correct={correct}"
            )


def _report(
    site: Site, learner: User, learner_2: User, learner_3: User, applicant: User
) -> None:
    course = Course.objects.get(slug=COURSE_SLUG, site=site)
    quiz = Form.objects.get(slug=QUIZ.slug, site=site)
    survey = Form.objects.get(slug=SURVEY.slug, site=site)
    form = Form.objects.get(slug=APPLICATION_FORM.slug, site=site)
    quiz_index = _item_index(course, quiz)
    survey_index = _item_index(course, survey)

    click.secho(f"\nSite: {site.name} ({site.domain})", fg="yellow", bold=True)
    click.secho(f"Course '{course.title}' slug={course.slug}", fg="yellow")
    click.echo(f"  /courses/{course.slug}/")
    click.secho(f"Quiz '{quiz.title}' index={quiz_index} pk={quiz.pk}", fg="yellow")
    click.echo(f"  start:   /courses/{course.slug}/{quiz_index}/")
    click.echo(f"  results: /courses/{course.slug}/{quiz_index}/complete")
    _report_versions(quiz)
    s1, *_later = _sittings(learner, quiz)
    _describe(f"S1 ({learner.email})", s1)
    s2, *_later = _sittings(learner_2, quiz)
    _describe(f"S2 ({learner_2.email})", s2)
    click.echo(
        f"  {learner_3.email}: {len(_sittings(learner_3, quiz))} sittings "
        "(registered, quiz not yet sat)"
    )

    click.secho(
        f"Survey '{survey.title}' index={survey_index} pk={survey.pk}", fg="yellow"
    )
    click.echo(f"  start: /courses/{course.slug}/{survey_index}/")
    _report_versions(survey)
    survey_sitting, *_later = _sittings(learner, survey)
    _describe(f"Survey sitting ({learner.email})", survey_sitting)

    application = (
        CourseApplication.objects.filter(
            user=applicant,
            course__slug=APPLICATION_COURSE_SLUG,
            state__in=ACTIVE_STATES,
        )
        .select_related("course", "form_progress")
        .first()
    )
    click.secho(f"Application form '{form.title}' pk={form.pk}", fg="yellow")
    _report_versions(form)
    if application is None or application.form_progress is None:
        click.secho(f"  {applicant.email} has no active application.", fg="red")
        return
    click.secho(
        f"Application {application.pk} by {applicant.email} on "
        f"'{application.course.title}' slug={application.course.slug} "
        f"state={application.state}",
        fg="yellow",
    )
    click.echo(
        "  check-your-answers: "
        + reverse("course_applications:check_answers", kwargs={"pk": application.pk})
    )
    _describe("Application sitting", application.form_progress)
    click.echo(
        f"\nLogins (password = email): {learner.email}, {learner_2.email}, "
        f"{learner_3.email}, {applicant.email}"
    )


@click.command()
@click.option(
    "--site-name",
    default="DemoDev",
    help="Site name to create the data on (default: 'DemoDev').",
)
def command(site_name: str) -> None:
    """Seed the question-versions browser-QA scenario."""
    site = _get_site(site_name)
    _pin_current_site(site)
    with _site_context(site):
        learner, _ = _get_or_create_user(site, LEARNER_EMAIL, "Vera", "Versions")
        learner_2, _ = _get_or_create_user(site, LEARNER_2_EMAIL, "Victor", "Versions")
        learner_3, _ = _get_or_create_user(site, LEARNER_3_EMAIL, "Vince", "Versions")
        applicant, _ = _get_or_create_user(site, APPLICANT_EMAIL, "Ava", "Applicant")
        course = _get_or_create_course(site, COURSE_SLUG, COURSE_TITLE)
        _register(learner, course, site)
        _register(learner_2, course, site)
        _register(learner_3, course, site)
        _seed_quiz(site, course, learner, learner_2)
        _seed_survey(site, course, learner)
        _seed_application(site, applicant)
        _report(site, learner, learner_2, learner_3, applicant)
