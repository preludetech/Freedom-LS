"""Seed the browser-QA scenario for quiz served papers (shuffled, recorded papers).

Creates (idempotently) on one site (default: DemoDev):

1. "QA Served Paper Course", whose items in order are:

   1. "QA Served Paper Quiz" - QUIZ, 3 titled pages, pass mark 70,
      ``quiz_show_incorrect`` on, ``submit_on_exit`` off. Page 1 holds a content
      block then a multiple-choice question; page 2 a checkboxes and a dropdown
      question; page 3 a multiple-choice question. Every question has four
      options "Option A".."Option D" in authored order.
   2. "QA Served Paper Submit-on-exit Quiz" - QUIZ, ``submit_on_exit`` on, two
      pages with one multiple-choice question each.
   3. "QA Served Paper Survey" - UNSCORED, two pages with one question each.

2. Learners A, B and D (none has sat anything) and learner C, all in the cohort
   "QA Served Paper Cohort", which is registered on the course. Passwords equal
   the email address.
3. Learner C's one completed sitting of quiz 1 as a sitting finished before
   served papers existed would look: answers recorded, ``asked`` and ``scores``
   written by ``complete()`` (3/4: the dropdown is answered wrong), then
   ``served_paper`` nulled and the times backdated.
4. Two application-gated courses, each with a two-page application form: one
   QUIZ-strategy form and one UNSCORED form.

Sequential unlock applies: items 2 and 3 of the course stay BLOCKED for a
learner until they pass item 1.

Every content row (form, page, content block, question, course, category)
gets a plausible ``file_path`` under ``qa/served_paper/``, because the admin
requires one to save. A re-run fills any that are blank and changes nothing
else, so page and option orders edited during QA survive.

A re-run creates nothing twice. It does not clear sittings that browser QA left
behind; use ``qa_clear_form_sittings`` for that (the summary flags them).

Usage:
    uv run python manage.py qa_create_served_paper_scenario
    uv run python manage.py qa_create_served_paper_scenario --site-name DemoDev
"""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import cast

import djclick as click

from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
)
from freedom_ls.content_engine.models import Course, CourseCategory
from freedom_ls.form_engine.factories import (
    FormContentFactory,
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
)
from freedom_ls.form_engine.models import (
    Form,
    FormContent,
    FormPage,
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionAnswer,
    QuestionType,
)
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.learner_management.models import Cohort
from freedom_ls.learner_progress.attempts import ensure_attempt
from freedom_ls.learner_progress.models import CourseFormAttempt
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.qa_helpers.management.commands.qa_create_multiselect_quiz_scoring import (
    _add_member,
    _add_options,
    _collection_item_for,
    _get_or_create_user,
    _get_site,
    _item_index,
    _record_for,
    _register_cohort,
)

OPTION_LETTERS = ["A", "B", "C", "D"]


@dataclass(frozen=True)
class QuestionSpec:
    text: str
    type: str
    # Letters of the correct options; empty for a non-quiz question.
    correct: tuple[str, ...] = ()


@dataclass(frozen=True)
class PageSpec:
    title: str
    questions: list[QuestionSpec]
    content: str = ""


@dataclass(frozen=True)
class FormSpec:
    title: str
    slug: str
    strategy: str
    pages: list[PageSpec]
    quiz_pass_percentage: int | None = None
    quiz_show_incorrect: bool = False
    submit_on_exit: bool = False


@dataclass(frozen=True)
class LearnerSpec:
    label: str
    email: str


@dataclass
class BuiltForm:
    form: Form
    questions: list[FormQuestion] = field(default_factory=list)


COURSE_TITLE = "QA Served Paper Course"
COURSE_SLUG = "qa-served-paper-course"
COHORT_NAME = "QA Served Paper Cohort"

MAIN_QUIZ = FormSpec(
    title="QA Served Paper Quiz",
    slug="qa-served-paper-quiz",
    strategy=FormStrategy.QUIZ,
    quiz_pass_percentage=70,
    quiz_show_incorrect=True,
    submit_on_exit=False,
    pages=[
        PageSpec(
            title="Page 1: Warm up",
            content=(
                "This content block comes first on page 1, before the "
                "multiple-choice question."
            ),
            questions=[
                QuestionSpec(
                    "Q1 (multiple choice): which option is correct?",
                    QuestionType.MULTIPLE_CHOICE,
                    ("B",),
                )
            ],
        ),
        PageSpec(
            title="Page 2: Checkboxes and dropdown",
            questions=[
                QuestionSpec(
                    "Q2 (checkboxes): tick every correct option.",
                    QuestionType.CHECKBOXES,
                    ("A", "C"),
                ),
                QuestionSpec(
                    "Q3 (dropdown): pick the correct option.",
                    QuestionType.DROPDOWN,
                    ("D",),
                ),
            ],
        ),
        PageSpec(
            title="Page 3: Last question",
            questions=[
                QuestionSpec(
                    "Q4 (multiple choice): which option is correct?",
                    QuestionType.MULTIPLE_CHOICE,
                    ("C",),
                )
            ],
        ),
    ],
)

SUBMIT_ON_EXIT_QUIZ = FormSpec(
    title="QA Served Paper Submit-on-exit Quiz",
    slug="qa-served-paper-submit-on-exit-quiz",
    strategy=FormStrategy.QUIZ,
    quiz_pass_percentage=50,
    quiz_show_incorrect=True,
    submit_on_exit=True,
    pages=[
        PageSpec(
            title="Exit quiz page 1",
            questions=[
                QuestionSpec(
                    "Exit Q1 (multiple choice): which option is correct?",
                    QuestionType.MULTIPLE_CHOICE,
                    ("A",),
                )
            ],
        ),
        PageSpec(
            title="Exit quiz page 2",
            questions=[
                QuestionSpec(
                    "Exit Q2 (multiple choice): which option is correct?",
                    QuestionType.MULTIPLE_CHOICE,
                    ("D",),
                )
            ],
        ),
    ],
)

SURVEY = FormSpec(
    title="QA Served Paper Survey",
    slug="qa-served-paper-survey",
    strategy=FormStrategy.UNSCORED,
    pages=[
        PageSpec(
            title="Survey page 1",
            questions=[
                QuestionSpec(
                    "Survey Q1: which option do you prefer?",
                    QuestionType.MULTIPLE_CHOICE,
                )
            ],
        ),
        PageSpec(
            title="Survey page 2",
            questions=[
                QuestionSpec(
                    "Survey Q2: anything else to tell us?", QuestionType.SHORT_TEXT
                )
            ],
        ),
    ],
)

QUIZ_APPLICATION_FORM = FormSpec(
    title="QA Served Paper Quiz Application Form",
    slug="qa-served-paper-quiz-application-form",
    strategy=FormStrategy.QUIZ,
    quiz_pass_percentage=50,
    quiz_show_incorrect=True,
    pages=[
        PageSpec(
            title="Application quiz page 1",
            questions=[
                QuestionSpec(
                    "Application Q1 (multiple choice): which option is correct?",
                    QuestionType.MULTIPLE_CHOICE,
                    ("B",),
                )
            ],
        ),
        PageSpec(
            title="Application quiz page 2",
            questions=[
                QuestionSpec(
                    "Application Q2 (multiple choice): which option is correct?",
                    QuestionType.MULTIPLE_CHOICE,
                    ("C",),
                )
            ],
        ),
    ],
)

PLAIN_APPLICATION_FORM = FormSpec(
    title="QA Served Paper Plain Application Form",
    slug="qa-served-paper-plain-application-form",
    strategy=FormStrategy.UNSCORED,
    pages=[
        PageSpec(
            title="Application page 1",
            questions=[
                QuestionSpec("What is your full name?", QuestionType.SHORT_TEXT)
            ],
        ),
        PageSpec(
            title="Application page 2",
            questions=[
                QuestionSpec("Why do you want to join?", QuestionType.SHORT_TEXT)
            ],
        ),
    ],
)

# (slug, title, application form)
APPLICATION_COURSES: list[tuple[str, str, FormSpec]] = [
    (
        "qa-served-paper-quiz-application-course",
        "QA Served Paper Quiz Application Course",
        QUIZ_APPLICATION_FORM,
    ),
    (
        "qa-served-paper-plain-application-course",
        "QA Served Paper Plain Application Course",
        PLAIN_APPLICATION_FORM,
    ),
]

LEARNERS = [
    LearnerSpec("A", "qa_served_a@email.com"),
    LearnerSpec("B", "qa_served_b@email.com"),
    LearnerSpec("D", "qa_served_d@email.com"),
]
OLD_SITTING_LEARNER = LearnerSpec("C", "qa_served_c@email.com")

# Learner C's answers to the main quiz, by question order: Q3 (dropdown) is
# answered wrong, so the stored score is 3/4 = 75%, a pass at 70.
OLD_SITTING_ANSWERS: list[tuple[str, ...]] = [("B",), ("A", "C"), ("A",), ("C",)]
OLD_SITTING_DAYS_AGO = 30

FILE_PATH_ROOT = "qa/served_paper"
CATEGORY_SLUG = "qa-served-paper-applications"


def _file_path(*parts: str) -> str:
    """A plausible source-file path for a scenario row; the admin requires one."""
    return "/".join([FILE_PATH_ROOT, *parts])


def _page_file_path(form_slug: str, page_slug: str) -> str:
    return _file_path(form_slug, f"{page_slug}.md")


def _child_file_path(form_slug: str, page_slug: str, kind: str, order: int) -> str:
    return _file_path(form_slug, page_slug, f"{kind}-{order}.md")


def _fill_blank_file_paths(form: Form) -> None:
    """Give the form and its pages, content blocks and questions a file_path
    where it is blank. Writes only file_path, so QA edits to order survive."""
    Form.objects.filter(pk=form.pk, file_path="").update(
        file_path=_file_path(form.slug, "form.md")
    )
    for page in form.pages.all():
        FormPage.objects.filter(pk=page.pk, file_path="").update(
            file_path=_page_file_path(form.slug, page.slug)
        )
        for model, kind in ((FormContent, "content"), (FormQuestion, "question")):
            for child in model.objects.filter(form_page=page, file_path=""):
                model.objects.filter(pk=child.pk).update(
                    file_path=_child_file_path(form.slug, page.slug, kind, child.order)
                )


def _build_form(spec: FormSpec, site: Site) -> BuiltForm:
    """Create the form from its spec, or return the existing one by slug."""
    form: Form | None = Form.objects.filter(slug=spec.slug, site=site).first()
    if form is None:
        form = cast(
            Form,
            FormFactory(
                title=spec.title,
                slug=spec.slug,
                strategy=spec.strategy,
                file_path=_file_path(spec.slug, "form.md"),
                quiz_pass_percentage=spec.quiz_pass_percentage,
                quiz_show_incorrect=spec.quiz_show_incorrect,
                submit_on_exit=spec.submit_on_exit,
                site=site,
            ),
        )
        for page_order, page_spec in enumerate(spec.pages, start=1):
            page_slug = f"{spec.slug}-page-{page_order}"
            page = cast(
                FormPage,
                FormPageFactory(
                    form=form,
                    title=page_spec.title,
                    slug=page_slug,
                    file_path=_page_file_path(spec.slug, page_slug),
                    order=page_order,
                    site=site,
                ),
            )
            child_order = 1
            if page_spec.content:
                FormContentFactory(
                    form_page=page,
                    content=page_spec.content,
                    file_path=_child_file_path(
                        spec.slug, page_slug, "content", child_order
                    ),
                    order=child_order,
                    site=site,
                )
                child_order += 1
            for question_spec in page_spec.questions:
                question = cast(
                    FormQuestion,
                    FormQuestionFactory(
                        form_page=page,
                        question=question_spec.text,
                        type=question_spec.type,
                        required=True,
                        file_path=_child_file_path(
                            spec.slug, page_slug, "question", child_order
                        ),
                        order=child_order,
                        site=site,
                    ),
                )
                child_order += 1
                if question_spec.type != QuestionType.SHORT_TEXT:
                    options = [
                        (
                            f"Option {letter}",
                            letter in question_spec.correct
                            if spec.strategy == FormStrategy.QUIZ
                            else False,
                        )
                        for letter in OPTION_LETTERS
                    ]
                    _add_options(question, options, site)
    _fill_blank_file_paths(form)
    questions = list(
        FormQuestion.objects.filter(form_page__form=form)
        .prefetch_related("options")
        .order_by("form_page__order", "order")
    )
    return BuiltForm(form=form, questions=questions)


def _course_file_path(slug: str) -> str:
    return _file_path("courses", f"{slug}.md")


def _fill_blank_course_file_path(course: Course) -> None:
    Course.objects.filter(pk=course.pk, file_path="").update(
        file_path=_course_file_path(course.slug)
    )


def _get_or_create_course(site: Site) -> Course:
    existing: Course | None = Course.objects.filter(slug=COURSE_SLUG, site=site).first()
    if existing is not None:
        _fill_blank_course_file_path(existing)
        return existing
    return cast(
        Course,
        CourseFactory(
            title=COURSE_TITLE,
            slug=COURSE_SLUG,
            description="QA course for quiz served papers.",
            file_path=_course_file_path(COURSE_SLUG),
            site=site,
        ),
    )


def _place_forms(course: Course, forms: list[Form], site: Site) -> None:
    placed = {item.child_id for item in course.items.all()}
    for order, form in enumerate(forms):
        if form.pk not in placed:
            ContentCollectionItemFactory(
                collection_object=course, child_object=form, order=order, site=site
            )


def _get_or_create_application_course(
    site: Site, slug: str, title: str, form: Form, category: CourseCategory
) -> Course:
    fields = {
        "title": title,
        "description": f"Application-gated QA course; application form: {form.title}.",
        "access_config": {
            "access_type": "application_gated",
            "application_form": f"../{form.slug}/form.md",
        },
        "application_form": form,
        "dashboard_category": category,
    }
    course: Course | None = Course.objects.filter(slug=slug, site=site).first()
    if course is None:
        course = cast(
            Course,
            CourseFactory(
                slug=slug, site=site, file_path=_course_file_path(slug), **fields
            ),
        )
    else:
        _fill_blank_course_file_path(course)
        for name, value in fields.items():
            setattr(course, name, value)
        course.save(update_fields=list(fields.keys()))
    course.categories.set([category])
    return course


def _get_or_create_cohort(site: Site) -> Cohort:
    existing: Cohort | None = Cohort.objects.filter(name=COHORT_NAME, site=site).first()
    if existing is not None:
        return existing
    return cast(
        Cohort,
        CohortFactory(
            name=COHORT_NAME, site=site, organisation=get_default_organisation(site)
        ),
    )


def _old_sitting(
    user: User, course: Course, built: BuiltForm, site: Site
) -> FormProgress:
    """Learner C's completed, pre-served-paper sitting of the main quiz. Idempotent."""
    record = _record_for(user, course)
    collection_item = _collection_item_for(course, built.form)
    sitting = ensure_attempt(record, collection_item)
    if sitting.completed_time is not None:
        # Already seeded (or sat in QA): a re-run leaves an existing sitting alone.
        return sitting
    for question, letters in zip(built.questions, OLD_SITTING_ANSWERS, strict=True):
        chosen = [
            option
            for option in question.options.order_by("order")
            if option.text.removeprefix("Option ") in letters
        ]
        answer: QuestionAnswer | None = QuestionAnswer.objects.filter(
            form_progress=sitting, question=question
        ).first()
        if answer is None:
            answer = cast(
                QuestionAnswer,
                QuestionAnswerFactory(
                    form_progress=sitting, question=question, site=site
                ),
            )
        answer.selected_options.set(chosen)
    sitting.complete()
    # complete() writes the served paper first; a sitting finished before served
    # papers existed has none. start_time is auto_now_add, so backdating goes
    # through the queryset too.
    completed_at = timezone.now() - timedelta(days=OLD_SITTING_DAYS_AGO)
    FormProgress.objects.filter(pk=sitting.pk).update(
        served_paper=None,
        furthest_page=built.form.pages.last(),
        start_time=completed_at - timedelta(minutes=15),
        completed_time=completed_at,
    )
    sitting.refresh_from_db()
    return sitting


def _sitting_count(user: User, course: Course) -> int:
    return CourseFormAttempt.objects.filter(
        course_progress__learner__user=user, course_progress__course=course
    ).count()


def _print_form(built: BuiltForm) -> None:
    form = built.form
    click.secho(f"\nForm '{form.title}'  pk={form.pk}", fg="cyan", bold=True)
    click.echo(
        f"  strategy={form.strategy}  pass%={form.quiz_pass_percentage}  "
        f"show_incorrect={form.quiz_show_incorrect}  "
        f"submit_on_exit={form.submit_on_exit}"
    )
    for page in form.pages.order_by("order"):
        click.echo(f"  Page {page.order}: '{page.title}'  pk={page.pk}")
        for child in page.children():
            if not isinstance(child, FormQuestion):
                click.echo(f"    [content block] pk={child.pk}")
                continue
            click.echo(f"    [{child.type}] '{child.question}'  pk={child.pk}")
            for option in child.options.order_by("order"):
                mark = "CORRECT" if option.correct else "-"
                click.echo(f"      {option.text}  pk={option.pk}  {mark}")


@click.command()
@click.option(
    "--site-name",
    default="DemoDev",
    help="Site name to create the data on (default: 'DemoDev').",
)
def command(site_name: str) -> None:
    """Seed the served-paper browser-QA courses, forms, learners and old sitting."""
    site = _get_site(site_name)

    main_quiz = _build_form(MAIN_QUIZ, site)
    exit_quiz = _build_form(SUBMIT_ON_EXIT_QUIZ, site)
    survey = _build_form(SURVEY, site)
    course = _get_or_create_course(site)
    _place_forms(course, [main_quiz.form, exit_quiz.form, survey.form], site)
    course = Course.objects.get(pk=course.pk)

    cohort = _get_or_create_cohort(site)
    _register_cohort(cohort, course, site)
    learners: list[tuple[LearnerSpec, User]] = []
    for spec in [*LEARNERS, OLD_SITTING_LEARNER]:
        user, _created = _get_or_create_user(site, spec.email, "Learner", spec.label)
        _add_member(user, cohort, site)
        learners.append((spec, user))

    old_user = learners[-1][1]
    old_sitting = _old_sitting(old_user, course, main_quiz, site)

    category_file_path = _file_path("categories", f"{CATEGORY_SLUG}.md")
    category, _ = CourseCategory.objects.get_or_create(
        site=site,
        slug=CATEGORY_SLUG,
        defaults={
            "title": "QA Served Paper Applications",
            "file_path": category_file_path,
        },
    )
    CourseCategory.objects.filter(pk=category.pk, file_path="").update(
        file_path=category_file_path
    )
    application_courses: list[tuple[Course, BuiltForm]] = []
    for slug, title, form_spec in APPLICATION_COURSES:
        built = _build_form(form_spec, site)
        application_courses.append(
            (
                _get_or_create_application_course(
                    site, slug, title, built.form, category
                ),
                built,
            )
        )

    click.secho("\n--- Served paper QA data ---", fg="cyan", bold=True)
    click.secho(f"Site: {site.name} ({site.domain}) [id {site.pk}]", fg="cyan")
    click.secho(f"Cohort: '{cohort.name}'  pk={cohort.pk}", fg="cyan")
    for spec, user in learners:
        sittings = _sitting_count(user, course)
        flag = ""
        if spec in LEARNERS and sittings:
            flag = "  <-- has sittings; clear with qa_clear_form_sittings"
        click.secho(
            f"Learner {spec.label}: {user.email} / {user.email}  "
            f"sittings on course={sittings}{flag}",
            fg="green",
        )
    click.secho(f"\nCourse '{course.title}'  /courses/{course.slug}/", fg="cyan")
    for built in (main_quiz, exit_quiz, survey):
        index = _item_index(course, built.form)
        click.echo(
            f"  item {index}: /courses/{course.slug}/{index}/  {built.form.title}"
        )
    for built in (main_quiz, exit_quiz, survey):
        _print_form(built)

    click.secho(
        f"\nLearner C old sitting: FormProgress pk={old_sitting.pk}  "
        f"completed={old_sitting.completed_time}  scores={old_sitting.scores}  "
        f"served_paper={old_sitting.served_paper}  "
        f"answers={old_sitting.answers.count()}",
        fg="green",
    )

    for app_course, built in application_courses:
        click.secho(
            f"\nApplication course '{app_course.title}'  "
            f"detail /courses/{app_course.slug}/detail/  "
            f"apply /applications/apply/{app_course.slug}/",
            fg="cyan",
        )
        _print_form(built)
