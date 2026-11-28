"""Seed the browser-QA scenario for the educator quiz attempt review page.

Creates, idempotently, on one site (default: DemoDev):

1. "QA Attempt Review Course", placing in order:

   1. Quiz A - QUIZ, pass mark 60, shuffle pages/questions/options on. Page 1
      holds a content block, a multiple-choice question and a checkboxes
      question; page 2 an optional dropdown question and a long-text question
      (no correct option, so it never scores).
   2. Quiz B - QUIZ, no pass mark.
   3. Quiz C - QUIZ, pass mark 50.
   4. Quiz D - QUIZ, pass mark 50, its third question optional.
   5. A survey - UNSCORED.

2. The admin (demodev@email.com) as organisation admin of the site's default
   organisation and of a second organisation.
3. Learner L1 in the default organisation, registered individually, with:
   three completed sittings of Quiz A (failed, passed, one with the optional
   dropdown left unanswered) and one in progress, each served a paper whose
   page, question and option order differs from the authored order; a legacy
   Quiz B sitting (``served_paper`` and ``asked`` nulled); a Quiz C sitting
   after which the correct option of one question moved; a Quiz D sitting
   after which its unanswered served question was deleted; a completed survey.
4. Learner L2 in the second organisation, registered individually, with one
   completed Quiz A sitting.
5. Cohorts C1 and C2 in the default organisation, both registered on the
   course; a learner in each (the C2 one is L3) with one completed Quiz A
   sitting; educator E holding ``cohort_viewer`` on C1 only.

Every sitting goes through ``get_or_create_incomplete`` (so it has its
CourseFormAttempt), ``build_served_paper`` (the product's own shuffler) and
``complete()`` (so ``asked`` and ``scores`` are what the product writes).
Passwords equal the email address.

A re-run creates nothing twice: a learner who already has sittings on the
course is left alone, and the quiz edits are only made right after the
sitting they follow is seeded.

Usage:
    uv run python manage.py qa_create_attempt_review_scenario
    uv run python manage.py qa_create_attempt_review_scenario --site-name DemoDev
"""

from collections.abc import Callable
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
from freedom_ls.content_engine.models import Course
from freedom_ls.form_engine.conditions import ServedPaper
from freedom_ls.form_engine.factories import (
    FormContentFactory,
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import (
    Form,
    FormContent,
    FormPage,
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionAnswer,
    QuestionOption,
    QuestionType,
)
from freedom_ls.form_engine.served_paper import build_served_paper
from freedom_ls.learner_management.factories import (
    CohortFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_progress.attempts import get_or_create_incomplete
from freedom_ls.learner_progress.models import CourseFormAttempt
from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.qa_helpers.management.commands.qa_create_multiselect_quiz_scoring import (
    _add_member,
    _collection_item_for,
    _get_or_create_user,
    _get_site,
    _item_index,
    _record_for,
    _register_cohort,
)
from freedom_ls.qa_helpers.management.commands.qa_create_organisation_scenarios import (
    _pin_current_site,
    _site_context,
)
from freedom_ls.role_based_permissions.utils import assign_object_role

ADMIN_EMAIL = "demodev@email.com"
SECOND_ORGANISATION_SLUG = "harbour-college"
COURSE_TITLE = "QA Attempt Review Course"
COURSE_SLUG = "qa-attempt-review-course"
FILE_PATH_ROOT = "qa/attempt_review"
SERVED_PAPER_TRIES = 1000


@dataclass(frozen=True)
class OptionSpec:
    text: str
    correct: bool = False


@dataclass(frozen=True)
class QuestionSpec:
    # A short handle the answer plans below use to name the question.
    slot: str
    text: str
    type: str
    options: tuple[OptionSpec, ...] = ()
    required: bool = True


@dataclass(frozen=True)
class PageSpec:
    title: str
    questions: tuple[QuestionSpec, ...]
    content: str = ""


@dataclass(frozen=True)
class FormSpec:
    title: str
    slug: str
    strategy: str
    pages: tuple[PageSpec, ...]
    quiz_pass_percentage: int | None = None
    shuffle: bool = False
    # The folder the form's plausible source-file paths sit under.
    file_path_root: str = FILE_PATH_ROOT


@dataclass
class BuiltForm:
    form: Form
    questions: dict[str, FormQuestion] = field(default_factory=dict)

    def option(self, slot: str, text: str) -> QuestionOption:
        return self.questions[slot].options.get(text=text)


@dataclass(frozen=True)
class PersonSpec:
    label: str
    email: str
    first_name: str
    last_name: str


# An answer plan: question slot -> option texts chosen, or the typed text for a
# free-text question. A slot left out is left unanswered.
AnswerPlan = dict[str, tuple[str, ...] | str]


QUIZ_A = FormSpec(
    title="QA Attempt Review Quiz A",
    slug="qa-attempt-review-quiz-a",
    strategy=FormStrategy.QUIZ,
    quiz_pass_percentage=60,
    shuffle=True,
    pages=(
        PageSpec(
            title="Instruments and checks",
            content="Read each question carefully before you answer.",
            questions=(
                QuestionSpec(
                    "mc",
                    "Which instrument shows the aircraft's altitude?",
                    QuestionType.MULTIPLE_CHOICE,
                    (
                        OptionSpec("Altimeter", True),
                        OptionSpec("Airspeed indicator"),
                        OptionSpec("Heading indicator"),
                        OptionSpec("Turn coordinator"),
                    ),
                ),
                QuestionSpec(
                    "cb",
                    "Which of these are part of a pre-flight walk-around?",
                    QuestionType.CHECKBOXES,
                    (
                        OptionSpec("Check the fuel quantity", True),
                        OptionSpec("Inspect the control surfaces", True),
                        OptionSpec("Switch on the cabin radio"),
                        OptionSpec("Order the in-flight meal"),
                    ),
                ),
            ),
        ),
        PageSpec(
            title="Rules and briefing",
            questions=(
                QuestionSpec(
                    "dd",
                    "What does VFR stand for?",
                    QuestionType.DROPDOWN,
                    (
                        OptionSpec("Visual Flight Rules", True),
                        OptionSpec("Variable Flight Range"),
                        OptionSpec("Vertical Flight Route"),
                        OptionSpec("Visual Frequency Radio"),
                    ),
                    required=False,
                ),
                QuestionSpec(
                    "lt",
                    "Describe how you would brief a passenger before take-off.",
                    QuestionType.LONG_TEXT,
                ),
            ),
        ),
    ),
)

QUIZ_B = FormSpec(
    title="QA Attempt Review Quiz B (legacy)",
    slug="qa-attempt-review-quiz-b",
    strategy=FormStrategy.QUIZ,
    pages=(
        PageSpec(
            title="Weather basics",
            questions=(
                QuestionSpec(
                    "b1",
                    "Which cloud type usually brings thunderstorms?",
                    QuestionType.MULTIPLE_CHOICE,
                    (
                        OptionSpec("Cumulonimbus", True),
                        OptionSpec("Cirrus"),
                        OptionSpec("Stratus"),
                    ),
                ),
                QuestionSpec(
                    "b2",
                    "What does a METAR report?",
                    QuestionType.MULTIPLE_CHOICE,
                    (
                        OptionSpec("Current aerodrome weather", True),
                        OptionSpec("Fuel prices"),
                        OptionSpec("Runway lighting faults"),
                    ),
                ),
            ),
        ),
    ),
)

QUIZ_C = FormSpec(
    title="QA Attempt Review Quiz C (changed)",
    slug="qa-attempt-review-quiz-c",
    strategy=FormStrategy.QUIZ,
    quiz_pass_percentage=50,
    pages=(
        PageSpec(
            title="Radio calls",
            questions=(
                QuestionSpec(
                    "c1",
                    "Which word confirms you have received a message?",
                    QuestionType.MULTIPLE_CHOICE,
                    (
                        OptionSpec("Roger", True),
                        OptionSpec("Mayday"),
                        OptionSpec("Standby"),
                    ),
                ),
                QuestionSpec(
                    "c2",
                    "Which squawk code signals a radio failure?",
                    QuestionType.MULTIPLE_CHOICE,
                    (
                        OptionSpec("7600", True),
                        OptionSpec("7700"),
                        OptionSpec("7500"),
                    ),
                ),
            ),
        ),
    ),
)
# After L1's Quiz C sitting, c2's correct option moves from "7600" to "7700".
QUIZ_C_CHANGED_SLOT = "c2"
QUIZ_C_OLD_CORRECT = "7600"
QUIZ_C_NEW_CORRECT = "7700"

QUIZ_D = FormSpec(
    title="QA Attempt Review Quiz D (deleted item)",
    slug="qa-attempt-review-quiz-d",
    strategy=FormStrategy.QUIZ,
    quiz_pass_percentage=50,
    pages=(
        PageSpec(
            title="Airspace",
            questions=(
                QuestionSpec(
                    "d1",
                    "Which airspace class is uncontrolled?",
                    QuestionType.MULTIPLE_CHOICE,
                    (
                        OptionSpec("Class G", True),
                        OptionSpec("Class A"),
                        OptionSpec("Class C"),
                    ),
                ),
                QuestionSpec(
                    "d2",
                    "What does CTR stand for?",
                    QuestionType.MULTIPLE_CHOICE,
                    (
                        OptionSpec("Control zone", True),
                        OptionSpec("Central traffic route"),
                        OptionSpec("Climb to release"),
                    ),
                ),
                QuestionSpec(
                    "d3",
                    "Which chart shows airspace boundaries?",
                    QuestionType.MULTIPLE_CHOICE,
                    (
                        OptionSpec("Aeronautical chart", True),
                        OptionSpec("Road map"),
                        OptionSpec("Tide table"),
                    ),
                    required=False,
                ),
            ),
        ),
    ),
)
# L1 leaves d3 unanswered (an answered question is PROTECTed from deletion),
# then d3 is deleted from the quiz.
QUIZ_D_DELETED_SLOT = "d3"

SURVEY = FormSpec(
    title="QA Attempt Review Survey",
    slug="qa-attempt-review-survey",
    strategy=FormStrategy.UNSCORED,
    pages=(
        PageSpec(
            title="Your feedback",
            questions=(
                QuestionSpec(
                    "s1",
                    "How useful was this course?",
                    QuestionType.MULTIPLE_CHOICE,
                    (
                        OptionSpec("Very useful"),
                        OptionSpec("Somewhat useful"),
                        OptionSpec("Not useful"),
                    ),
                ),
                QuestionSpec(
                    "s2", "Anything else to tell us?", QuestionType.SHORT_TEXT
                ),
            ),
        ),
    ),
)

BRIEFING = "Point out the exits, the seat belt and where the fire extinguisher is."

QUIZ_A_FAIL: AnswerPlan = {
    "mc": ("Airspeed indicator",),
    "cb": ("Check the fuel quantity",),
    "dd": ("Variable Flight Range",),
    "lt": BRIEFING,
}
QUIZ_A_PASS: AnswerPlan = {
    "mc": ("Altimeter",),
    "cb": ("Check the fuel quantity", "Inspect the control surfaces"),
    "dd": ("Visual Flight Rules",),
    "lt": BRIEFING,
}
QUIZ_A_UNANSWERED: AnswerPlan = {
    "mc": ("Altimeter",),
    "cb": ("Check the fuel quantity", "Inspect the control surfaces"),
    "lt": BRIEFING,
}
QUIZ_A_IN_PROGRESS: AnswerPlan = {"mc": ("Heading indicator",)}
QUIZ_B_ANSWERS: AnswerPlan = {"b1": ("Cumulonimbus",), "b2": ("Fuel prices",)}
QUIZ_C_ANSWERS: AnswerPlan = {"c1": ("Roger",), "c2": ("7600",)}
QUIZ_D_ANSWERS: AnswerPlan = {"d1": ("Class G",), "d2": ("Control zone",)}
SURVEY_ANSWERS: AnswerPlan = {
    "s1": ("Somewhat useful",),
    "s2": "More practice questions, please.",
}

L1 = PersonSpec("L1", "qa_review_l1@email.com", "Lerato", "Mokoena")
L2 = PersonSpec("L2", "qa_review_l2@email.com", "Liam", "Naidoo")
L3 = PersonSpec("L3", "qa_review_l3@email.com", "Lungi", "Dube")
C1_LEARNER = PersonSpec("C1 learner", "qa_review_c1@email.com", "Carla", "Botha")
EDUCATOR = PersonSpec("E", "qa_review_educator@email.com", "Esi", "Mensah")
C1_NAME = "QA Attempt Review C1"
C2_NAME = "QA Attempt Review C2"


def _file_path(*parts: str, root: str = FILE_PATH_ROOT) -> str:
    """A plausible source-file path; the admin requires one to save a row."""
    return "/".join([root, *parts])


def _create_form(spec: FormSpec, site: Site) -> Form:
    form = cast(
        Form,
        FormFactory(
            title=spec.title,
            slug=spec.slug,
            strategy=spec.strategy,
            file_path=_file_path(spec.slug, "form.md", root=spec.file_path_root),
            quiz_pass_percentage=spec.quiz_pass_percentage,
            quiz_show_incorrect=spec.strategy == FormStrategy.QUIZ,
            shuffle_pages=spec.shuffle,
            shuffle_questions=spec.shuffle,
            shuffle_options=spec.shuffle,
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
                file_path=_file_path(
                    spec.slug, f"{page_slug}.md", root=spec.file_path_root
                ),
                order=page_order,
                site=site,
            ),
        )
        child_order = 1
        if page_spec.content:
            FormContentFactory(
                form_page=page,
                content=page_spec.content,
                file_path=_file_path(
                    spec.slug, page_slug, "content-1.md", root=spec.file_path_root
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
                    required=question_spec.required,
                    file_path=_file_path(
                        spec.slug,
                        page_slug,
                        f"{question_spec.slot}.md",
                        root=spec.file_path_root,
                    ),
                    order=child_order,
                    site=site,
                ),
            )
            child_order += 1
            for option_order, option_spec in enumerate(question_spec.options):
                QuestionOptionFactory(
                    question=question,
                    text=option_spec.text,
                    value=str(option_order + 1),
                    order=option_order,
                    correct=(
                        option_spec.correct
                        if spec.strategy == FormStrategy.QUIZ
                        else None
                    ),
                    site=site,
                )
    return form


def _build_form(spec: FormSpec, site: Site) -> BuiltForm:
    """Create the form from its spec, or return the existing one by slug."""
    form: Form | None = Form.objects.filter(slug=spec.slug, site=site).first()
    if form is None:
        form = _create_form(spec, site)
    by_text = {q.question: q for q in FormQuestion.objects.filter(form_page__form=form)}
    questions = {
        question_spec.slot: by_text[question_spec.text]
        for page_spec in spec.pages
        for question_spec in page_spec.questions
        if question_spec.text in by_text
    }
    return BuiltForm(form=form, questions=questions)


def _get_or_create_course(site: Site) -> Course:
    existing: Course | None = Course.objects.filter(slug=COURSE_SLUG, site=site).first()
    if existing is not None:
        return existing
    return cast(
        Course,
        CourseFactory(
            title=COURSE_TITLE,
            slug=COURSE_SLUG,
            description="QA course for the educator quiz attempt review page.",
            file_path=_file_path("courses", f"{COURSE_SLUG}.md"),
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


def _ensure_cohort(site: Site, organisation: Organisation, name: str) -> Cohort:
    existing: Cohort | None = Cohort.objects.filter(name=name, site=site).first()
    if existing is not None:
        return existing
    return cast(Cohort, CohortFactory(name=name, site=site, organisation=organisation))


def _register_individually(
    user: User, organisation: Organisation, course: Course, site: Site
) -> None:
    learner = cast(
        Learner, LearnerFactory(user=user, organisation=organisation, site=site)
    )
    if not LearnerCourseRegistration.objects.filter(
        learner=learner, course=course, site=site
    ).exists():
        LearnerCourseRegistrationFactory(learner=learner, course=course, site=site)


def _differs_everywhere(form: Form) -> Callable[[ServedPaper], bool]:
    """True for a paper whose every shuffleable order differs from authored."""
    pages = list(form.pages.order_by("order"))
    page_ids = [str(page.id) for page in pages]
    children = {str(page.id): [str(c.id) for c in page.children()] for page in pages}
    options = {
        str(question.id): [str(o.id) for o in question.options.order_by("order")]
        for question in FormQuestion.objects.filter(form_page__form=form)
    }

    def wanted(paper: ServedPaper) -> bool:
        if len(page_ids) > 1 and [p["id"] for p in paper["pages"]] == page_ids:
            return False
        for page in paper["pages"]:
            authored = children[page["id"]]
            if len(authored) > 1 and page["children"] == authored:
                return False
        return all(
            len(options[question_id]) <= 1 or served != options[question_id]
            for question_id, served in paper["options"].items()
        )

    return wanted


def _write_served_paper(
    sitting: FormProgress, wanted: Callable[[ServedPaper], bool] | None
) -> None:
    """Serve the sitting a paper built by the product's own shuffler.

    With `wanted`, keep building until a paper satisfies it, so QA sees an
    order that visibly differs from the authored one.
    """
    paper = build_served_paper(sitting.form)
    if wanted is not None:
        for _ in range(SERVED_PAPER_TRIES):
            if wanted(paper):
                break
            paper = build_served_paper(sitting.form)
        else:
            raise click.ClickException(
                f"No served paper of '{sitting.form.title}' met the wanted order."
            )
    FormProgress.objects.filter(pk=sitting.pk, served_paper__isnull=True).update(
        served_paper=paper
    )
    sitting.refresh_from_db()


def _answer(
    sitting: FormProgress, built: BuiltForm, plan: AnswerPlan, site: Site
) -> None:
    for slot, value in plan.items():
        answer = cast(
            QuestionAnswer,
            QuestionAnswerFactory(
                form_progress=sitting, question=built.questions[slot], site=site
            ),
        )
        if isinstance(value, str):
            answer.text_answer = value
            answer.save(update_fields=["text_answer"])
        else:
            answer.selected_options.set([built.option(slot, text) for text in value])


def _page_id(sitting: FormProgress, form: Form, *, last: bool) -> str:
    """The first or last page the sitting was served (authored order without a paper)."""
    if sitting.served_paper:
        paper = cast(ServedPaper, sitting.served_paper)
        return paper["pages"][-1 if last else 0]["id"]
    pages = list(form.pages.order_by("order"))
    return str(pages[-1 if last else 0].pk)


def _sit(
    user: User,
    course: Course,
    built: BuiltForm,
    plan: AnswerPlan,
    site: Site,
    *,
    started_days_ago: float,
    complete: bool = True,
    differs: bool = False,
) -> FormProgress:
    """One sitting of `built` in the learner's course record, through the
    product's own attempt, serving and completion code, then backdated."""
    record = _record_for(user, course)
    sitting = get_or_create_incomplete(record, _collection_item_for(course, built.form))
    if built.form.strategy == FormStrategy.QUIZ:
        _write_served_paper(
            sitting, _differs_everywhere(built.form) if differs else None
        )
    _answer(sitting, built, plan, site)
    started = timezone.now() - timedelta(days=started_days_ago)
    if not complete:
        # start_time is auto_now_add, so backdating goes through the queryset.
        FormProgress.objects.filter(pk=sitting.pk).update(
            start_time=started,
            furthest_page_id=_page_id(sitting, built.form, last=False),
        )
        sitting.refresh_from_db()
        return sitting
    sitting.complete()
    sitting.refresh_from_db()
    FormProgress.objects.filter(pk=sitting.pk).update(
        start_time=started,
        completed_time=started + timedelta(minutes=12),
        furthest_page_id=_page_id(sitting, built.form, last=True),
    )
    sitting.refresh_from_db()
    return sitting


def _sittings_of(user: User, course: Course) -> list[FormProgress]:
    return list(
        FormProgress.objects.filter(
            course_attempt__course_progress__learner__user=user,
            course_attempt__course_progress__course=course,
        )
        .select_related("form")
        .order_by("start_time")
    )


def _has_sittings(user: User, course: Course) -> bool:
    return CourseFormAttempt.objects.filter(
        course_progress__learner__user=user, course_progress__course=course
    ).exists()


def _seed_l1(
    user: User, course: Course, forms: dict[str, BuiltForm], site: Site
) -> None:
    quiz_a = forms["A"]
    for plan, days_ago in (
        (QUIZ_A_FAIL, 10),
        (QUIZ_A_PASS, 7),
        (QUIZ_A_UNANSWERED, 3),
    ):
        _sit(user, course, quiz_a, plan, site, started_days_ago=days_ago, differs=True)
    _sit(
        user,
        course,
        quiz_a,
        QUIZ_A_IN_PROGRESS,
        site,
        started_days_ago=0.05,
        complete=False,
        differs=True,
    )

    legacy = _sit(user, course, forms["B"], QUIZ_B_ANSWERS, site, started_days_ago=30)
    # A sitting finished before served papers and the asked record existed.
    FormProgress.objects.filter(pk=legacy.pk).update(served_paper=None, asked=None)

    _sit(user, course, forms["C"], QUIZ_C_ANSWERS, site, started_days_ago=5)
    changed = forms["C"].questions[QUIZ_C_CHANGED_SLOT]
    changed.options.filter(text=QUIZ_C_OLD_CORRECT).update(correct=False)
    changed.options.filter(text=QUIZ_C_NEW_CORRECT).update(correct=True)

    _sit(user, course, forms["D"], QUIZ_D_ANSWERS, site, started_days_ago=4)
    forms["D"].questions.pop(QUIZ_D_DELETED_SLOT).delete()

    _sit(user, course, forms["S"], SURVEY_ANSWERS, site, started_days_ago=2)


@click.command()
@click.option(
    "--site-name",
    default="DemoDev",
    help="Site name to create the data on (default: 'DemoDev').",
)
def command(site_name: str) -> None:
    """Seed the attempt-review browser-QA course, quizzes, learners and sittings."""
    site = _get_site(site_name)
    _pin_current_site(site)
    with _site_context(site):
        _seed_and_report(site)


def _seed_and_report(site: Site) -> None:
    first_org = get_default_organisation(site)
    second_org = Organisation.objects.get(site=site, slug=SECOND_ORGANISATION_SLUG)
    admin = User.objects.get(email=ADMIN_EMAIL)
    for organisation in (first_org, second_org):
        assign_object_role(admin, organisation, "organisation_admin", assigned_by=admin)

    forms = {
        "A": _build_form(QUIZ_A, site),
        "B": _build_form(QUIZ_B, site),
        "C": _build_form(QUIZ_C, site),
        "D": _build_form(QUIZ_D, site),
        "S": _build_form(SURVEY, site),
    }
    course = _get_or_create_course(site)
    _place_forms(course, [built.form for built in forms.values()], site)
    course = Course.objects.get(pk=course.pk)

    users: dict[str, User] = {}
    for spec in (L1, L2, L3, C1_LEARNER, EDUCATOR):
        users[spec.label], _created = _get_or_create_user(
            site, spec.email, spec.first_name, spec.last_name
        )

    _register_individually(users[L1.label], first_org, course, site)
    _register_individually(users[L2.label], second_org, course, site)
    c1 = _ensure_cohort(site, first_org, C1_NAME)
    c2 = _ensure_cohort(site, first_org, C2_NAME)
    for cohort, spec in ((c1, C1_LEARNER), (c2, L3)):
        _register_cohort(cohort, course, site)
        _add_member(users[spec.label], cohort, site)
    assign_object_role(users[EDUCATOR.label], c1, "cohort_viewer", assigned_by=admin)

    if not _has_sittings(users[L1.label], course):
        _seed_l1(users[L1.label], course, forms, site)
    for spec in (L2, L3, C1_LEARNER):
        if not _has_sittings(users[spec.label], course):
            _sit(
                users[spec.label],
                course,
                forms["A"],
                QUIZ_A_PASS,
                site,
                started_days_ago=6,
            )

    _report(site, (first_org, second_org), course, forms, users, (c1, c2))


def _verdict(sitting: FormProgress) -> str:
    if sitting.completed_time is None:
        return "IN PROGRESS"
    if sitting.form.strategy != FormStrategy.QUIZ:
        return "completed (non-quiz)"
    try:
        percentage = sitting.quiz_percentage()
    except ValueError:
        return f"scores={sitting.scores}"
    if sitting.form.quiz_pass_percentage is None:
        verdict = "no pass mark"
    else:
        verdict = "PASS" if sitting.passed() else "FAIL"
    scores = sitting.scores or {}
    return f"{scores['score']}/{scores['max_score']} = {percentage}% {verdict}"


def _print_served_paper(sitting: FormProgress) -> None:
    paper = sitting.served_paper
    if not paper:
        click.echo("    served_paper: null")
        return
    answers = {
        answer.question_id: answer
        for answer in sitting.answers.prefetch_related("selected_options")
    }
    for number, page in enumerate(paper["pages"], start=1):
        form_page = FormPage.objects.get(pk=page["id"])
        click.echo(
            f"    Served page {number}: '{form_page.title}' (authored {form_page.order})"
        )
        for child_id in page["children"]:
            question: FormQuestion | None = FormQuestion.objects.filter(
                pk=child_id
            ).first()
            if question is None:
                content: FormContent | None = FormContent.objects.filter(
                    pk=child_id
                ).first()
                click.echo(
                    f"      [content] {content.content if content else '(deleted)'}"
                )
                continue
            answer = answers.get(question.id)
            click.echo(f"      [{question.type}] {question.question}")
            if not paper["options"].get(child_id):
                typed = answer.text_answer if answer else "(unanswered)"
                click.echo(f"        typed: {typed}")
                continue
            chosen = (
                {option.id for option in answer.selected_options.all()}
                if answer
                else set()
            )
            for option_id in paper["options"][child_id]:
                option = QuestionOption.objects.get(pk=option_id)
                marks = [
                    mark
                    for mark, on in (
                        ("SELECTED", option.id in chosen),
                        ("CORRECT", option.correct is True),
                    )
                    if on
                ]
                click.echo(f"        - {option.text}  {' '.join(marks)}")
            if answer is None:
                click.echo("        (unanswered)")


def _report(
    site: Site,
    organisations: tuple[Organisation, Organisation],
    course: Course,
    forms: dict[str, BuiltForm],
    users: dict[str, User],
    cohorts: tuple[Cohort, Cohort],
) -> None:
    click.secho("\n--- Attempt review QA data ---", fg="cyan", bold=True)
    click.echo(f"Site: {site.name} ({site.domain}) [id {site.pk}]")
    for label, organisation in zip(("First", "Second"), organisations, strict=True):
        click.echo(
            f"{label} organisation: {organisation.name} slug={organisation.slug} "
            f"/educator/organisations/{organisation.slug}/"
        )
    click.echo(f"Course: '{course.title}' slug={course.slug} pk={course.pk}")
    for built in forms.values():
        index = _item_index(course, built.form)
        click.echo(
            f"  item {index} /courses/{course.slug}/{index}/: '{built.form.title}' "
            f"pk={built.form.pk} strategy={built.form.strategy} "
            f"pass%={built.form.quiz_pass_percentage}"
        )
    for name, cohort in zip(("C1", "C2"), cohorts, strict=True):
        click.echo(f"Cohort {name}: '{cohort.name}' pk={cohort.pk}")
    for label, user in users.items():
        learners = Learner.objects.filter(user=user).select_related("organisation")
        learner_pks = ", ".join(
            f"{learner.pk} ({learner.organisation.slug})" for learner in learners
        )
        click.secho(
            f"\n{label}: {user.display_name} | {user.email} / {user.email} | "
            f"user pk={user.pk} | learner pk={learner_pks or '-'}",
            fg="green",
        )
        for sitting in _sittings_of(user, course):
            click.echo(
                f"  sitting {sitting.pk}  '{sitting.form.title}'  "
                f"started={sitting.start_time:%Y-%m-%d %H:%M}  {_verdict(sitting)}  "
                f"served_paper={'yes' if sitting.served_paper else 'null'}  "
                f"asked={'yes' if sitting.asked else 'null'}"
            )
    completed_quiz_a = [
        sitting
        for sitting in _sittings_of(users[L1.label], course)
        if sitting.form_id == forms["A"].form.pk and sitting.completed_time
    ]
    for number, sitting in enumerate(completed_quiz_a, start=1):
        click.secho(
            f"\nL1 Quiz A attempt {number} ({sitting.pk}) served paper:", fg="cyan"
        )
        _print_served_paper(sitting)
