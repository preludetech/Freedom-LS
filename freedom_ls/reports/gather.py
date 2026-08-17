"""Batched, site-explicit data gathering for the cohort progress report.

This is the only layer that touches the ORM for report generation. It builds a
plain, frozen `CohortReportData` tree; the render layer (a later batch) walks
that tree and never queries. See the dataclasses below for the contract.

Runs from a background task, which has no HTTP request, so
`SiteAwareManager.get_queryset()` cannot filter by site on its own — every
query here filters explicitly on `site_id=site_id`.
"""

from __future__ import annotations

import dataclasses
import statistics
from collections import defaultdict
from datetime import datetime
from typing import cast
from uuid import UUID

from django.contrib.sites.models import Site
from django.db.models import Count, F, Window
from django.db.models.functions import RowNumber
from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import (
    FREE_TEXT_QUESTION_TYPES,
    Form,
    FormQuestion,
    FormStrategy,
    QuestionOption,
    Topic,
)
from freedom_ls.reports.at_risk import AT_RISK_RULES, StudentDetailLike
from freedom_ls.reports.config import config
from freedom_ls.site_aware_models.config import config as site_config
from freedom_ls.student_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
)
from freedom_ls.student_progress.models import (
    FormProgress,
    QuestionAnswer,
    TopicProgress,
    attempt_completes_form,
    evaluate_quiz_answers,
)

ATTENTION_LIST_MAX = 12
CONFUSIONS_PER_QUIZ_MAX = 10
MIN_RESPONDENTS_FOR_PERCENTAGE = 10

# Free-text answers have no correctness concept at all, so they are excluded
# from wrong-answer aggregation and the confusion tally entirely, not scored
# wrong by default. The set itself lives with QuestionType in content_engine,
# so this module and the student results page cannot drift apart on it.


class ReportTooLargeError(Exception):
    """Raised when a cohort has more members than `config.REPORTS_MAX_STUDENTS`."""


@dataclasses.dataclass(frozen=True)
class QuizAttempt:
    """One completed sitting of a quiz."""

    attempt_number: int
    completed_at: datetime
    score: int | None
    max_score: int | None
    percentage: int | None
    passed: bool | None


@dataclasses.dataclass(frozen=True)
class QuizResult:
    form_id: UUID
    title: str
    latest_score: int | None
    latest_max_score: int | None
    latest_percentage: int | None
    passed: bool | None
    attempt_count: int
    completed_at: datetime | None
    # Chronological, oldest first, so a student's own section can show whether
    # retries improved on the first sitting. Built from the same rows the
    # latest_* fields above are read from, so the two cannot disagree.
    attempts: list[QuizAttempt]


@dataclasses.dataclass(frozen=True)
class WrongAnswer:
    question_number: int
    question_text: str
    times_wrong: int
    selected_option_texts: list[str]
    correct_option_texts: list[str]


@dataclasses.dataclass(frozen=True)
class CompletedItem:
    title: str
    completed_at: datetime
    is_quiz: bool


@dataclasses.dataclass(frozen=True)
class QuizColumn:
    form_id: UUID
    title: str
    abbreviation: str
    pass_percentage: int | None


@dataclasses.dataclass(frozen=True)
class StudentRow:
    user_id: int
    full_name: str
    completion_percentage: int
    completed_item_count: int
    total_item_count: int
    last_completed_title: str | None
    last_completed_at: datetime | None
    quiz_cells: dict[UUID, QuizResult | None]


@dataclasses.dataclass(frozen=True)
class SummaryRow:
    user_id: int
    full_name: str
    completion_percentage: int
    completed_item_count: int
    total_item_count: int
    last_completed_title: str | None
    last_completed_at: datetime | None
    # One entry per quiz in the owning SummaryTable, in the same order.
    cells: list[QuizResult | None]


@dataclasses.dataclass(frozen=True)
class SummaryTable:
    quizzes: list[QuizColumn]
    rows: list[SummaryRow]
    continued: bool


@dataclasses.dataclass(frozen=True)
class QuizWrongAnswers:
    form_id: UUID
    title: str
    answers: list[WrongAnswer]


@dataclasses.dataclass(frozen=True)
class AtRiskFlag:
    rule_id: str
    label: str
    reason: str
    # A role token name, so the report can weight a badge by how serious the
    # flag is. Read off the rule with a fallback, never required of it — see
    # where the flags are built.
    severity: str


@dataclasses.dataclass(frozen=True)
class StudentDetail:
    user_id: int
    full_name: str
    sort_key: tuple[str, str]
    completion_percentage: int
    completed_item_count: int
    total_item_count: int
    last_completed_title: str | None
    last_completed_at: datetime | None
    has_any_progress: bool
    completed_items: list[CompletedItem]
    quiz_results: list[QuizResult]
    wrong_answers: list[QuizWrongAnswers]
    # The single instant the whole report is evaluated against, carried on
    # every student so at-risk rules (freedom_ls.reports.at_risk) never
    # call timezone.now() themselves — see AtRiskRule.evaluate().
    report_generated_at: datetime
    flags: list[AtRiskFlag]

    @property
    def has_reportable_activity(self) -> bool:
        """Whether the student's own section has a body to draw.

        Narrower than `has_any_progress`, which is true the moment a progress
        row exists: a student who opened a topic without finishing it has a row
        but nothing to print, and the section must say so rather than end.
        """
        return bool(self.completed_items or self.quiz_results or self.wrong_answers)


@dataclasses.dataclass(frozen=True)
class QuizConfusion:
    question_number: int
    question_text: str
    respondent_count: int
    wrong_count: int
    show_percentage: bool
    # Populated only when show_percentage is True, None otherwise -- keeping
    # the threshold invariant in one place (gather_cohort_report_data) rather
    # than leaving templates to compute a percentage themselves.
    wrong_percentage: int | None
    distractors: list[tuple[str, int]]
    correct_option_texts: list[str]


@dataclasses.dataclass(frozen=True)
class ConfusionBlock:
    questions: list[QuizConfusion]
    shown: int
    total: int


@dataclasses.dataclass(frozen=True)
class AttentionList:
    students: list[StudentDetail]
    shown: int
    total: int


@dataclasses.dataclass(frozen=True)
class CourseSection:
    course_id: UUID
    title: str
    is_active: bool
    item_count: int
    quizzes: list[QuizColumn]
    student_rows: list[StudentRow]
    # `quizzes` chunked at config.REPORTS_MAX_QUIZ_COLUMNS, so a wide course
    # splits across several tables instead of overflowing the landscape page.
    # Always at least one table, even for a course with no quizzes at all.
    summary_tables: list[SummaryTable]
    confusions_by_quiz: dict[UUID, ConfusionBlock]


@dataclasses.dataclass(frozen=True)
class CohortReportData:
    cohort_name: str
    # Who the report is from: the tenant's own display name, which is the only
    # organisation identity FLS records. Whoever runs the platform underneath
    # it is a separate, optional setting the render layer reads.
    site_name: str
    powered_by_name: str | None
    generated_at: datetime
    requested_by_name: str
    courses: list[CourseSection]
    students: list[StudentDetail]
    attention_list: AttentionList
    cohort_size: int
    median_completion: int
    not_started_count: int
    complete_count: int


def _abbreviate_quiz_title(title: str) -> str:
    """Short column-header form of a quiz title; the legend under the table spells it out.

    A trailing numeric token is kept whole -- "Hydrology Quiz 12" is `HQ12`, not
    `HQ1`; dropping a digit both loses the quiz number and invites collisions
    between quizzes whose numbers share a leading digit.
    """
    words = [word for word in title.split() if word]
    if not words:
        return ""
    number = words[-1] if words[-1].isdigit() else ""
    name_words = words[:-1] if number else words
    if not name_words:
        return number
    if len(name_words) == 1 and not number:
        return name_words[0][:4].upper()
    initials = "".join(word[0] for word in name_words[:4]).upper()
    return f"{initials}{number}"


def _unique_abbreviations(titles: list[str]) -> list[str]:
    """Abbreviations for one course's quizzes, disambiguated so no two collide."""
    taken: set[str] = set()
    abbreviations: list[str] = []
    for title in titles:
        base = _abbreviate_quiz_title(title)
        abbreviation = base
        suffix = 2
        while abbreviation in taken:
            abbreviation = f"{base}-{suffix}"
            suffix += 1
        taken.add(abbreviation)
        abbreviations.append(abbreviation)
    return abbreviations


def _chunk_quiz_columns(
    quizzes: list[QuizColumn], max_columns: int
) -> list[list[QuizColumn]]:
    """Split quiz columns into page-sized groups, always yielding at least one group.

    A course with no quizzes still gets one (empty) group so its Student /
    Completion / Last-item columns still render.
    """
    if not quizzes:
        return [[]]
    return [
        quizzes[start : start + max_columns]
        for start in range(0, len(quizzes), max_columns)
    ]


def _student_sort_key(user: User) -> tuple[str, str]:
    """Surname-first ordering, falling back to the email when no surname is set."""
    first_name = (user.first_name or "").strip()
    last_name = (user.last_name or "").strip()
    return (last_name or user.email, first_name)


def _completion_counts(
    items: list[Topic | Form],
    user_id: int,
    completed_topic_ids_by_user: dict[int, set[UUID]],
    completed_form_ids_by_user: dict[int, set[UUID]],
) -> tuple[int, int]:
    """(completed_count, total_count) for one student over the given items."""
    completed_topic_ids = completed_topic_ids_by_user.get(user_id, set())
    completed_form_ids = completed_form_ids_by_user.get(user_id, set())
    completed = 0
    for item in items:
        ids = completed_topic_ids if isinstance(item, Topic) else completed_form_ids
        if item.id in ids:
            completed += 1
    return completed, len(items)


def _latest_completion(
    items: list[Topic | Form],
    user_id: int,
    topic_complete_time: dict[tuple[int, UUID], datetime],
    latest_form_progress: dict[tuple[int, UUID], FormProgress],
    completed_attempts_by_user_form: dict[tuple[int, UUID], list[FormProgress]],
) -> tuple[str | None, datetime | None]:
    """Most recent completion timestamp and title among the given items for one student.

    Never CourseProgress.last_accessed_item — that tracks last viewed, not
    last completed.
    """
    best_title: str | None = None
    best_at: datetime | None = None
    for item in items:
        if isinstance(item, Topic):
            at = topic_complete_time.get((user_id, item.id))
        else:
            key = (user_id, item.id)
            at = (
                latest_form_progress[key].completed_time
                if completed_attempts_by_user_form.get(key)
                else None
            )
        if at is not None and (best_at is None or at > best_at):
            best_at, best_title = at, item.title
    return best_title, best_at


def _completed_items(
    items: list[Topic | Form],
    user_id: int,
    topic_complete_time: dict[tuple[int, UUID], datetime],
    latest_form_progress: dict[tuple[int, UUID], FormProgress],
    completed_attempts_by_user_form: dict[tuple[int, UUID], list[FormProgress]],
) -> list[CompletedItem]:
    completed: list[CompletedItem] = []
    for item in items:
        if isinstance(item, Topic):
            at = topic_complete_time.get((user_id, item.id))
            if at is not None:
                completed.append(
                    CompletedItem(title=item.title, completed_at=at, is_quiz=False)
                )
        else:
            key = (user_id, item.id)
            if completed_attempts_by_user_form.get(key):
                fp = latest_form_progress[key]
                # completed_attempts_by_user_form only collects rows with
                # completed_time set, and the ordering that produced "latest"
                # guarantees a completed row sorts first whenever one exists —
                # so completed_time is never None here.
                if fp.completed_time is not None:
                    completed.append(
                        CompletedItem(
                            title=item.title,
                            completed_at=fp.completed_time,
                            is_quiz=item.strategy == FormStrategy.QUIZ,
                        )
                    )
    return completed


def _score_attempt(
    fp: FormProgress, form: Form
) -> tuple[int | None, int | None, int | None, bool | None]:
    """One sitting's score, max score, percentage and verdict.

    The guard proven at educator_interface/views.py: quiz_percentage() raises
    on falsy scores, passed() raises when quiz_pass_percentage is unset, and
    quiz_pass_percentage is genuinely nullable. One implementation, so a
    sitting reads the same in the attempts table as in the summary cell.
    """
    score: int | None = None
    max_score: int | None = None
    percentage: int | None = None
    passed: bool | None = None
    if fp.completed_time and fp.scores:
        try:
            score = fp.scores.get("score")
            max_score = fp.scores.get("max_score")
            percentage = fp.quiz_percentage()
            passed = fp.passed() if form.quiz_pass_percentage is not None else None
        except (KeyError, ValueError):
            percentage = passed = None
    return score, max_score, percentage, passed


def _quiz_result_for(
    user_id: int,
    form: Form,
    latest_form_progress: dict[tuple[int, UUID], FormProgress],
    completed_attempts_by_user_form: dict[tuple[int, UUID], list[FormProgress]],
) -> QuizResult | None:
    """The student's completed attempts at this quiz, or None if never attempted."""
    key = (user_id, form.id)
    attempt_rows = completed_attempts_by_user_form.get(key, [])
    if not attempt_rows:
        return None

    attempts: list[QuizAttempt] = []
    for attempt_row in attempt_rows:
        completed_at = attempt_row.completed_time
        # Only rows with completed_time set are collected into this list; the
        # check is what narrows the Optional for the type checker.
        if completed_at is None:
            continue
        score, max_score, percentage, passed = _score_attempt(attempt_row, form)
        attempts.append(
            QuizAttempt(
                attempt_number=len(attempts) + 1,
                completed_at=completed_at,
                score=score,
                max_score=max_score,
                percentage=percentage,
                passed=passed,
            )
        )

    fp = latest_form_progress[key]
    latest_score, latest_max_score, percentage, passed = _score_attempt(fp, form)
    return QuizResult(
        form_id=form.id,
        title=form.title,
        latest_score=latest_score,
        latest_max_score=latest_max_score,
        latest_percentage=percentage,
        passed=passed,
        attempt_count=len(attempts),
        completed_at=fp.completed_time,
        attempts=attempts,
    )


def gather_cohort_report_data(
    cohort_id: str, site_id: int, *, requested_by_name: str = ""
) -> CohortReportData:
    """Assemble one cohort's report data with a fixed number of batched queries.

    No query runs inside a per-student or per-question loop — every id list is
    collected up front and every downstream lookup reads from an in-memory map
    built from a batched queryset.
    """
    now = timezone.now()

    cohort = Cohort.objects.get(pk=cohort_id, site_id=site_id)

    registrations = list(
        CohortCourseRegistration.objects.filter(cohort=cohort, site_id=site_id)
        .select_related("collection")
        .order_by("-is_active", "collection__title")
    )

    memberships = list(
        CohortMembership.objects.filter(cohort=cohort, site_id=site_id).select_related(
            "user"
        )
    )
    students_by_id: dict[int, User] = {m.user_id: m.user for m in memberships}
    # One ordering, computed once, used for the summary tables and the
    # per-student sections alike -- cohort membership query order would put the
    # summary table out of step with the Contents page and the student
    # sections, which are both alphabetical by surname.
    sort_key_by_id: dict[int, tuple[str, str]] = {
        user_id: _student_sort_key(user) for user_id, user in students_by_id.items()
    }
    student_ids = sorted(students_by_id, key=lambda user_id: sort_key_by_id[user_id])

    if len(student_ids) > config.REPORTS_MAX_STUDENTS:
        raise ReportTooLargeError(
            f"Cohort '{cohort.name}' has {len(student_ids)} students, exceeding "
            f"the configured limit of {config.REPORTS_MAX_STUDENTS} "
            "(REPORTS_MAX_STUDENTS)."
        )

    # Course items are gathered per course (one children() traversal each,
    # memoized on the instance) — bounded by course/CoursePart structure, not
    # by student or question counts. viewable_items() only excludes CoursePart
    # sentinels, so Activities are filtered out here, taking them out of the
    # completion denominator too (no ActivityProgress model exists).
    course_items: dict[UUID, list[Topic | Form]] = {}
    forms_by_id: dict[UUID, Form] = {}
    topic_ids: set[UUID] = set()
    form_ids: set[UUID] = set()
    quiz_form_ids: set[UUID] = set()
    # The order quizzes appear in their courses, which is the order the summary
    # table columns and a student's wrong-answer blocks both follow.
    ordered_quiz_form_ids: list[UUID] = []
    for reg in registrations:
        items = [
            item
            for item in reg.collection.viewable_items()
            if isinstance(item, Topic | Form)
        ]
        course_items[reg.collection_id] = items
        for item in items:
            if isinstance(item, Topic):
                topic_ids.add(item.id)
            else:
                form_ids.add(item.id)
                forms_by_id[item.id] = item
                if item.strategy == FormStrategy.QUIZ and item.id not in quiz_form_ids:
                    quiz_form_ids.add(item.id)
                    ordered_quiz_form_ids.append(item.id)

    topic_progress_rows = TopicProgress.objects.filter(
        site_id=site_id, user_id__in=student_ids, topic_id__in=topic_ids
    ).values_list("user_id", "topic_id", "complete_time")

    users_with_any_progress: set[int] = set()
    completed_topic_ids_by_user: dict[int, set[UUID]] = defaultdict(set)
    topic_complete_time: dict[tuple[int, UUID], datetime] = {}
    for user_id, topic_id, complete_time in topic_progress_rows:
        users_with_any_progress.add(user_id)
        if complete_time is not None:
            completed_topic_ids_by_user[user_id].add(topic_id)
            topic_complete_time[(user_id, topic_id)] = complete_time

    form_progress_rows = list(
        FormProgress.objects.filter(
            site_id=site_id, user_id__in=student_ids, form_id__in=form_ids
        )
        .select_related("form")
        .order_by(F("completed_time").desc(nulls_last=True), "-start_time")
    )

    latest_form_progress: dict[tuple[int, UUID], FormProgress] = {}
    # Every completed sitting, not merely how many there were: the per-student
    # attempts table reads from this, and a count would only have to be
    # reconciled against it later.
    completed_attempts_by_user_form: dict[tuple[int, UUID], list[FormProgress]] = (
        defaultdict(list)
    )
    completed_form_ids_by_user: dict[int, set[UUID]] = defaultdict(set)
    completed_attempt_ids: list[UUID] = []
    fp_user_form: dict[UUID, tuple[int, UUID]] = {}
    for fp in form_progress_rows:
        users_with_any_progress.add(fp.user_id)
        key = (fp.user_id, fp.form_id)
        fp_user_form[fp.id] = key
        if key not in latest_form_progress:
            latest_form_progress[key] = fp
        if fp.completed_time is not None:
            # Rows arrive newest-completed first, so the first completed sitting
            # seen for a key is the learner's latest — the one whose verdict
            # decides whether they are done with the form.
            is_latest_completed = key not in completed_attempts_by_user_form
            completed_attempts_by_user_form[key].append(fp)
            if is_latest_completed and attempt_completes_form(fp):
                completed_form_ids_by_user[fp.user_id].add(fp.form_id)
            completed_attempt_ids.append(fp.id)

    # The rows arrive newest-completed first; a reader of a student's section
    # wants their sittings in the order they sat them.
    for attempt_rows in completed_attempts_by_user_form.values():
        attempt_rows.reverse()

    # Filtering directly on a window annotation works from Django 4.2 onward.
    first_attempt_ids: set[UUID] = set(
        FormProgress.objects.filter(
            site_id=site_id,
            user_id__in=student_ids,
            form_id__in=quiz_form_ids,
            completed_time__isnull=False,
        )
        .annotate(
            rank=Window(
                RowNumber(),
                partition_by=[F("user_id"), F("form_id")],
                order_by=F("start_time").asc(),
            )
        )
        .filter(rank=1)
        .values_list("id", flat=True)
    )

    # DO NOT call FormQuestion.question_number() (re-queries per call) or
    # FormPage.children() (not prefetch-friendly) — question numbering is
    # computed here from one ordered, prefetched queryset instead.
    questions = list(
        FormQuestion.objects.filter(
            site_id=site_id, form_page__form_id__in=quiz_form_ids
        )
        .select_related("form_page")
        .prefetch_related("options")
        .order_by("form_page__order", "order")
    )
    question_ids = [question.id for question in questions]
    question_by_id: dict[UUID, FormQuestion] = {
        question.id: question for question in questions
    }
    options_by_question: dict[UUID, list[QuestionOption]] = {
        question.id: list(question.options.all()) for question in questions
    }
    correct_option_texts_by_question: dict[UUID, list[str]] = {
        question.id: [option.text for option in options if option.correct is True]
        for question, options in ((q, options_by_question[q.id]) for q in questions)
    }
    question_number_by_id: dict[UUID, int] = {}
    per_form_counter: dict[UUID, int] = defaultdict(int)
    for question in questions:
        form_id = question.form_page.form_id
        per_form_counter[form_id] += 1
        question_number_by_id[question.id] = per_form_counter[form_id]

    questions_by_form: dict[UUID, list[FormQuestion]] = defaultdict(list)
    for question in questions:
        questions_by_form[question.form_page.form_id].append(question)

    answers = list(
        QuestionAnswer.objects.filter(
            site_id=site_id,
            form_progress_id__in=completed_attempt_ids,
            # The attempt ids cover every form in the cohort's courses, quiz or
            # not. Without this, a survey answer would reach the question lookup
            # below, which only knows about quiz questions.
            question_id__in=question_ids,
        ).prefetch_related("selected_options")
    )
    selected_options_by_pair: dict[tuple[UUID, UUID], list[QuestionOption]] = {
        (answer.form_progress_id, answer.question_id): list(
            answer.selected_options.all()
        )
        for answer in answers
    }
    # A question left blank stores no answer row, so walking the rows alone would
    # drop it — while it still counts against the learner's score. Pair every
    # completed sitting with every question it covered instead, so a blank one is
    # judged as an empty selection rather than passed over.
    sat_pairs: list[tuple[UUID, FormQuestion]] = [
        (attempt_id, question)
        for attempt_id in completed_attempt_ids
        for question in questions_by_form.get(fp_user_form[attempt_id][1], [])
        if question.type not in FREE_TEXT_QUESTION_TYPES
    ]
    answer_rows = [
        (
            attempt_id,
            question.id,
            {
                option.id
                for option in selected_options_by_pair.get(
                    (attempt_id, question.id), []
                )
            },
        )
        for attempt_id, question in sat_pairs
    ]
    correctness = evaluate_quiz_answers(answer_rows, options_by_question)

    # `.exclude(correct=True)`, never `.filter(correct=False)`: correct is
    # nullable, and a correct=None option must still count as a distractor.
    distractor_rows = list(
        QuestionOption.objects.exclude(correct=True)
        .filter(
            site_id=site_id,
            question_id__in=question_ids,
            questionanswer__form_progress_id__in=first_attempt_ids,
        )
        .values("question_id", "id", "text")
        .annotate(times_selected=Count("questionanswer"))
        .order_by("question_id", "-times_selected")
    )
    distractors_by_question: dict[UUID, list[tuple[str, int]]] = defaultdict(list)
    for row in distractor_rows:
        question = question_by_id.get(row["question_id"])
        if question is None or question.type in FREE_TEXT_QUESTION_TYPES:
            continue
        distractors_by_question[row["question_id"]].append(
            (row["text"], row["times_selected"])
        )

    # Per-student wrong-answer detail, counted across every completed attempt.
    wrong_counts: dict[tuple[int, UUID, UUID], int] = defaultdict(int)
    wrong_selected_texts: dict[tuple[int, UUID, UUID], dict[str, None]] = defaultdict(
        dict
    )
    # Cohort-wide confusion tally, first attempts only.
    respondent_counts: dict[UUID, int] = defaultdict(int)
    wrong_counts_first: dict[UUID, int] = defaultdict(int)
    for attempt_id, question in sat_pairs:
        is_correct = correctness[(attempt_id, question.id)]
        user_id, form_id = fp_user_form[attempt_id]
        if not is_correct:
            wrong_key = (user_id, form_id, question.id)
            wrong_counts[wrong_key] += 1
            for option in selected_options_by_pair.get((attempt_id, question.id), []):
                wrong_selected_texts[wrong_key][option.text] = None
        if attempt_id in first_attempt_ids:
            respondent_counts[question.id] += 1
            if not is_correct:
                wrong_counts_first[question.id] += 1

    wrong_answers_by_user_quiz: dict[int, dict[UUID, list[WrongAnswer]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for (user_id, form_id, question_id), times_wrong in wrong_counts.items():
        wrong_answers_by_user_quiz[user_id][form_id].append(
            WrongAnswer(
                question_number=question_number_by_id[question_id],
                question_text=question_by_id[question_id].question,
                times_wrong=times_wrong,
                selected_option_texts=list(
                    wrong_selected_texts[(user_id, form_id, question_id)]
                ),
                correct_option_texts=correct_option_texts_by_question[question_id],
            )
        )
    for per_quiz in wrong_answers_by_user_quiz.values():
        for wrong_answer_list in per_quiz.values():
            wrong_answer_list.sort(key=lambda wa: wa.question_number)

    confusions_by_quiz: dict[UUID, ConfusionBlock] = {}
    for form_id in quiz_form_ids:
        candidates: list[tuple[float, FormQuestion, int, int]] = []
        for question in questions_by_form.get(form_id, []):
            if question.type in FREE_TEXT_QUESTION_TYPES:
                continue
            wrong = wrong_counts_first.get(question.id, 0)
            if wrong == 0:
                continue
            respondents = respondent_counts.get(question.id, 0)
            error_rate = wrong / respondents if respondents else 0.0
            candidates.append((error_rate, question, wrong, respondents))
        candidates.sort(key=lambda candidate: candidate[0], reverse=True)
        shown_candidates = candidates[:CONFUSIONS_PER_QUIZ_MAX]
        confusion_questions = []
        for _, question, wrong, respondents in shown_candidates:
            show_percentage = respondents >= MIN_RESPONDENTS_FOR_PERCENTAGE
            confusion_questions.append(
                QuizConfusion(
                    question_number=question_number_by_id[question.id],
                    question_text=question.question,
                    respondent_count=respondents,
                    wrong_count=wrong,
                    show_percentage=show_percentage,
                    wrong_percentage=round(wrong / respondents * 100)
                    if show_percentage
                    else None,
                    distractors=distractors_by_question.get(question.id, []),
                    correct_option_texts=correct_option_texts_by_question[question.id],
                )
            )
        confusions_by_quiz[form_id] = ConfusionBlock(
            questions=confusion_questions,
            shown=len(confusion_questions),
            total=len(candidates),
        )

    course_sections: list[CourseSection] = []
    for reg in registrations:
        course = reg.collection
        items = course_items[reg.collection_id]
        quiz_forms = [
            item
            for item in items
            if isinstance(item, Form) and item.strategy == FormStrategy.QUIZ
        ]
        abbreviations = _unique_abbreviations([form.title for form in quiz_forms])
        quiz_columns = [
            QuizColumn(
                form_id=form.id,
                title=form.title,
                abbreviation=abbreviation,
                pass_percentage=form.quiz_pass_percentage,
            )
            for form, abbreviation in zip(quiz_forms, abbreviations, strict=True)
        ]

        student_rows: list[StudentRow] = []
        for user_id in student_ids:
            completed_count, total_count = _completion_counts(
                items, user_id, completed_topic_ids_by_user, completed_form_ids_by_user
            )
            percentage = (
                round(completed_count / total_count * 100) if total_count else 0
            )
            last_title, last_at = _latest_completion(
                items,
                user_id,
                topic_complete_time,
                latest_form_progress,
                completed_attempts_by_user_form,
            )
            quiz_cells: dict[UUID, QuizResult | None] = {
                column.form_id: _quiz_result_for(
                    user_id,
                    forms_by_id[column.form_id],
                    latest_form_progress,
                    completed_attempts_by_user_form,
                )
                for column in quiz_columns
            }
            student_rows.append(
                StudentRow(
                    user_id=user_id,
                    full_name=students_by_id[user_id].display_name,
                    completion_percentage=percentage,
                    completed_item_count=completed_count,
                    total_item_count=total_count,
                    last_completed_title=last_title,
                    last_completed_at=last_at,
                    quiz_cells=quiz_cells,
                )
            )

        summary_tables = [
            SummaryTable(
                quizzes=chunk,
                rows=[
                    SummaryRow(
                        user_id=row.user_id,
                        full_name=row.full_name,
                        completion_percentage=row.completion_percentage,
                        completed_item_count=row.completed_item_count,
                        total_item_count=row.total_item_count,
                        last_completed_title=row.last_completed_title,
                        last_completed_at=row.last_completed_at,
                        cells=[row.quiz_cells[column.form_id] for column in chunk],
                    )
                    for row in student_rows
                ],
                continued=index > 0,
            )
            for index, chunk in enumerate(
                _chunk_quiz_columns(quiz_columns, config.REPORTS_MAX_QUIZ_COLUMNS)
            )
        ]

        course_sections.append(
            CourseSection(
                course_id=course.id,
                title=course.title,
                is_active=reg.is_active,
                item_count=len(items),
                quizzes=quiz_columns,
                student_rows=student_rows,
                summary_tables=summary_tables,
                confusions_by_quiz={
                    column.form_id: confusions_by_quiz.get(
                        column.form_id, ConfusionBlock(questions=[], shown=0, total=0)
                    )
                    for column in quiz_columns
                },
            )
        )

    all_items: list[Topic | Form] = [
        item for items in course_items.values() for item in items
    ]

    student_details: list[StudentDetail] = []
    for user_id in student_ids:
        user = students_by_id[user_id]
        completed_count, total_count = _completion_counts(
            all_items, user_id, completed_topic_ids_by_user, completed_form_ids_by_user
        )
        percentage = round(completed_count / total_count * 100) if total_count else 0
        last_title, last_at = _latest_completion(
            all_items,
            user_id,
            topic_complete_time,
            latest_form_progress,
            completed_attempts_by_user_form,
        )
        completed_items = _completed_items(
            all_items,
            user_id,
            topic_complete_time,
            latest_form_progress,
            completed_attempts_by_user_form,
        )
        quiz_results = [
            result
            for result in (
                _quiz_result_for(
                    user_id, form, latest_form_progress, completed_attempts_by_user_form
                )
                for form_id, form in forms_by_id.items()
                if form_id in quiz_form_ids
            )
            if result is not None
        ]

        wrong_answers_for_user = wrong_answers_by_user_quiz.get(user_id, {})
        wrong_answers = [
            QuizWrongAnswers(
                form_id=form_id,
                title=forms_by_id[form_id].title,
                answers=wrong_answers_for_user[form_id],
            )
            for form_id in ordered_quiz_form_ids
            if form_id in wrong_answers_for_user
        ]

        detail = StudentDetail(
            user_id=user_id,
            full_name=user.display_name,
            sort_key=sort_key_by_id[user_id],
            completion_percentage=percentage,
            completed_item_count=completed_count,
            total_item_count=total_count,
            last_completed_title=last_title,
            last_completed_at=last_at,
            has_any_progress=user_id in users_with_any_progress,
            completed_items=completed_items,
            quiz_results=quiz_results,
            wrong_answers=wrong_answers,
            report_generated_at=now,
            flags=[],
        )
        # Flags are evaluated exactly once, here, from one registry pass. The
        # attention list below filters and sorts this same list — it never
        # re-evaluates, so a student's flags read identically everywhere in
        # the report.
        # StudentDetailLike is a structural stand-in (freedom_ls/reports/at_risk.py);
        # StudentDetail satisfies it in practice but mypy can't confirm list
        # invariance and frozen-dataclass read-only attributes against a
        # Protocol declared with plain mutable fields, hence the cast.
        detail_for_rules = cast("StudentDetailLike", detail)
        flags = [
            AtRiskFlag(
                rule_id=rule.id,
                label=rule.label,
                reason=reason,
                severity=rule.severity,
            )
            for rule in AT_RISK_RULES
            for reason in [rule.evaluate(detail_for_rules)]
            if reason is not None
        ]
        student_details.append(dataclasses.replace(detail, flags=flags))

    flagged = sorted(
        (detail for detail in student_details if detail.flags),
        key=lambda detail: detail.completion_percentage,
    )
    shown_flagged = flagged[:ATTENTION_LIST_MAX]
    attention_list = AttentionList(
        students=shown_flagged, shown=len(shown_flagged), total=len(flagged)
    )

    completion_values = [detail.completion_percentage for detail in student_details]

    return CohortReportData(
        cohort_name=cohort.name,
        # HEADER_TITLE first, mirroring how the site header and outbound email
        # resolve the same name, so a project that renamed itself in one place
        # is not still called something else on its reports.
        site_name=site_config.HEADER_TITLE or Site.objects.get(pk=site_id).name,
        powered_by_name=config.REPORTS_POWERED_BY_NAME,
        generated_at=now,
        requested_by_name=requested_by_name,
        courses=course_sections,
        students=student_details,
        attention_list=attention_list,
        cohort_size=len(student_ids),
        median_completion=round(statistics.median(completion_values))
        if completion_values
        else 0,
        not_started_count=sum(1 for value in completion_values if value == 0),
        complete_count=sum(1 for value in completion_values if value == 100),
    )
