"""Assembly of the cohort progress report from batched, site-explicit queries.

`freedom_ls.reports.indexes` runs every query and returns frozen index bundles;
this module turns those bundles into the frozen `CohortReportData` tree defined
in `freedom_ls.reports.report_data`, and issues no queries of its own. The
render layer walks that tree and never queries either.

The report contract is re-exported here, so `from freedom_ls.reports.gather
import CohortReportData` keeps working; `report_data` is where it is defined.
"""

from __future__ import annotations

import dataclasses
import statistics
from collections import defaultdict
from datetime import datetime
from typing import cast
from uuid import UUID

from django.utils import timezone

from freedom_ls.content_engine.models import Topic
from freedom_ls.form_engine.models import (
    FREE_TEXT_QUESTION_TYPES,
    Form,
    FormProgress,
    FormQuestion,
    FormStrategy,
)
from freedom_ls.learner_management.models import CohortCourseRegistration
from freedom_ls.reports.at_risk import AT_RISK_RULES, LearnerDetailLike
from freedom_ls.reports.config import config
from freedom_ls.reports.indexes import (
    CohortRoster,
    CourseCatalogue,
    FormProgressIndex,
    ProgressIndex,
    QuestionIndex,
    SatQuestions,
    build_course_catalogue,
    build_question_index,
    build_sat_questions,
    index_distractors,
    load_cohort,
    load_distractor_rows,
    load_first_attempt_ids,
    load_organisation_logo_data_uri,
    load_progress_index,
    load_quiz_questions,
    load_registrations,
    load_roster,
    load_selected_options_by_pair,
    resolve_site_name,
)
from freedom_ls.reports.report_data import (
    ATTENTION_LIST_MAX,
    CONFUSIONS_PER_QUIZ_MAX,
    MIN_RESPONDENTS_FOR_PERCENTAGE,
    AtRiskFlag,
    AttentionList,
    CohortReportData,
    CompletedItem,
    ConfusionBlock,
    CourseSection,
    LearnerDetail,
    LearnerRow,
    OrganisationBrand,
    QuizAttempt,
    QuizColumn,
    QuizConfusion,
    QuizResult,
    QuizWrongAnswers,
    ReportTooLargeError,
    SelectedOption,
    SummaryRow,
    SummaryTable,
    WrongAnswer,
)

# The report contract, re-exported for the callers that have always imported it
# from this module. Naming them in __all__ is what stops ruff removing the
# imports as unused.
__all__ = [
    "ATTENTION_LIST_MAX",
    "CONFUSIONS_PER_QUIZ_MAX",
    "MIN_RESPONDENTS_FOR_PERCENTAGE",
    "AtRiskFlag",
    "AttentionList",
    "CohortReportData",
    "CompletedItem",
    "ConfusionBlock",
    "CourseSection",
    "LearnerDetail",
    "LearnerRow",
    "OrganisationBrand",
    "QuizAttempt",
    "QuizColumn",
    "QuizConfusion",
    "QuizResult",
    "QuizWrongAnswers",
    "ReportTooLargeError",
    "SelectedOption",
    "SummaryRow",
    "SummaryTable",
    "WrongAnswer",
    "gather_cohort_report_data",
]

# Free-text answers have no correctness concept at all, so they are excluded
# from wrong-answer aggregation and the confusion tally entirely, not scored
# wrong by default. The set itself lives with QuestionType in content_engine,
# so this module and the learner results page cannot drift apart on it.


@dataclasses.dataclass(frozen=True)
class QuizTallies:
    """Both views of the same answers, counted in one pass over the sat pairs."""

    # Per-learner wrong-answer detail, counted across every completed attempt.
    wrong_counts: dict[tuple[int, UUID, UUID], int]
    # (option text, its `correct` verdict) to the number of wrong attempts it was
    # selected in. A single attempt cannot select the same option twice, so a
    # count never exceeds the matching wrong_counts entry. The verdict rides in
    # the key so a multi-select answer's right ticks stay distinguishable from
    # the tick that cost the mark. Key order is first-seen order -- see the
    # ordering note on FormProgressIndex.completed_attempt_ids.
    wrong_selected_counts: dict[
        tuple[int, UUID, UUID], dict[tuple[str, bool | None], int]
    ]
    # Cohort-wide confusion tally, first attempts only.
    respondent_counts: dict[UUID, int]
    wrong_counts_first: dict[UUID, int]


@dataclasses.dataclass(frozen=True)
class CompletionStats:
    median_completion: int
    not_started_count: int
    complete_count: int


# Character budgets for the cover wordmark and the footer identity line. Each
# is paired with a specific print.css rule -- the wordmark slot's width cap,
# and the width the identity line has left beside the centred "Powered by"
# box -- that a downstream project cannot change independently of the number
# here, so these stay plain constants rather than a ReportsConfig Setting: a
# Setting would let the two drift out of step with the CSS they describe, and
# letting a downstream override just the number is not a degree of freedom the
# layout actually has.
#
# All three were set by rendering a ladder of real names -- short, at each
# threshold, 150 characters, one unbroken 100-character token, and Cyrillic --
# and reading the output, because a character count predicts neither how wide
# a name sets nor how many lines it takes.
WORDMARK_FULL_MAX_CHARS = 42
WORDMARK_CONDENSED_MAX_CHARS = 87
FOOTER_ORGANISATION_MAX_CHARS = 30


def _wordmark_size_class(name: str) -> str:
    """Which of print.css's two wordmark sizes this name is set at.

    WeasyPrint implements neither `text-overflow` nor `block-ellipsis`, so the
    stylesheet cannot rescue a long name at render time -- the size is a
    decision, made here, and asserted in a unit test.
    """
    return "full" if len(name) <= WORDMARK_FULL_MAX_CHARS else "condensed"


def _truncate_to_budget(text: str, max_chars: int) -> str:
    """`text` cut to `max_chars`, ending in a single ellipsis when it had to be.

    The cover wordmark slot and the footer identity line both hold a fixed
    amount of the organisation's name and neither can grow, so both need this;
    only the budget differs. One ellipsis character rather than three periods,
    because three periods cost three of the characters the budget was counting.
    """
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


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

    A course with no quizzes still gets one (empty) group so its Learner /
    Completion / Last-item columns still render.
    """
    if not quizzes:
        return [[]]
    return [
        quizzes[start : start + max_columns]
        for start in range(0, len(quizzes), max_columns)
    ]


def _completion_percentage(completed_count: int, total_count: int) -> int:
    """Whole-percent completion, and 0 rather than a division error for an empty course."""
    return round(completed_count / total_count * 100) if total_count else 0


def _completion_counts(
    items: list[Topic | Form], user_id: int, progress: ProgressIndex
) -> tuple[int, int]:
    """(completed_count, total_count) for one learner over the given items."""
    completed_topic_ids = progress.topics.completed_topic_ids_by_user.get(
        user_id, set()
    )
    completed_form_ids = progress.forms.completed_form_ids_by_user.get(user_id, set())
    completed = 0
    for item in items:
        ids = completed_topic_ids if isinstance(item, Topic) else completed_form_ids
        if item.id in ids:
            completed += 1
    return completed, len(items)


def _latest_completion(
    items: list[Topic | Form], user_id: int, progress: ProgressIndex
) -> tuple[str | None, datetime | None]:
    """Most recent completion timestamp and title among the given items for one learner.

    Never CourseProgress.last_accessed_item — that tracks last viewed, not
    last completed.
    """
    best_title: str | None = None
    best_at: datetime | None = None
    for item in items:
        if isinstance(item, Topic):
            at = progress.topics.complete_time.get((user_id, item.id))
        else:
            key = (user_id, item.id)
            at = (
                progress.forms.latest_by_user_form[key].completed_time
                if progress.forms.completed_attempts_by_user_form.get(key)
                else None
            )
        if at is not None and (best_at is None or at > best_at):
            best_at, best_title = at, item.title
    return best_title, best_at


def _completed_items(
    items: list[Topic | Form], user_id: int, progress: ProgressIndex
) -> list[CompletedItem]:
    completed: list[CompletedItem] = []
    for item in items:
        if isinstance(item, Topic):
            at = progress.topics.complete_time.get((user_id, item.id))
            if at is not None:
                completed.append(
                    CompletedItem(title=item.title, completed_at=at, is_quiz=False)
                )
        else:
            key = (user_id, item.id)
            if progress.forms.completed_attempts_by_user_form.get(key):
                fp = progress.forms.latest_by_user_form[key]
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

    The guard proven at educator_interface/views.py: quiz_percentage() raises on
    anything it cannot read a percentage out of, passed() raises when
    quiz_pass_percentage is unset, and quiz_pass_percentage is genuinely
    nullable. One implementation, so a sitting reads the same in the attempts
    table as in the summary cell.
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
        except ValueError:
            percentage = passed = None
    return score, max_score, percentage, passed


def _quiz_result_for(
    user_id: int, form: Form, forms: FormProgressIndex
) -> QuizResult | None:
    """The learner's completed attempts at this quiz, or None if never attempted."""
    key = (user_id, form.id)
    attempt_rows = forms.completed_attempts_by_user_form.get(key, [])
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

    # Safe to index rather than .get(): the attempt list above was non-empty,
    # and every completed sitting also set a latest row for the same key.
    fp = forms.latest_by_user_form[key]
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


def tally_quiz_answers(
    sat: SatQuestions, forms: FormProgressIndex, first_attempt_ids: set[UUID]
) -> QuizTallies:
    """One pass over the sat pairs, feeding both the per-learner and cohort views.

    The two views are counted together because they share this single walk;
    counting them apart would traverse every (sitting, question) pair twice.
    """
    wrong_counts: dict[tuple[int, UUID, UUID], int] = defaultdict(int)
    wrong_selected_counts: dict[
        tuple[int, UUID, UUID], dict[tuple[str, bool | None], int]
    ] = defaultdict(lambda: defaultdict(int))
    respondent_counts: dict[UUID, int] = defaultdict(int)
    wrong_counts_first: dict[UUID, int] = defaultdict(int)
    for attempt_id, question in sat.pairs:
        is_correct = sat.correctness[(attempt_id, question.id)]
        user_id, form_id = forms.user_form_by_attempt_id[attempt_id]
        if not is_correct:
            wrong_key = (user_id, form_id, question.id)
            wrong_counts[wrong_key] += 1
            for option in sat.selected_options_by_pair.get(
                (attempt_id, question.id), []
            ):
                wrong_selected_counts[wrong_key][(option.text, option.correct)] += 1
        if attempt_id in first_attempt_ids:
            respondent_counts[question.id] += 1
            if not is_correct:
                wrong_counts_first[question.id] += 1

    return QuizTallies(
        wrong_counts=wrong_counts,
        wrong_selected_counts=wrong_selected_counts,
        respondent_counts=respondent_counts,
        wrong_counts_first=wrong_counts_first,
    )


def build_wrong_answers_by_user_quiz(
    tallies: QuizTallies, questions: QuestionIndex
) -> dict[int, dict[UUID, list[WrongAnswer]]]:
    """Each learner's missed questions, grouped by quiz and ordered by question number."""
    wrong_answers_by_user_quiz: dict[int, dict[UUID, list[WrongAnswer]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for (user_id, form_id, question_id), times_wrong in tallies.wrong_counts.items():
        wrong_answers_by_user_quiz[user_id][form_id].append(
            WrongAnswer(
                question_number=questions.number_by_id[question_id],
                question_text=questions.by_id[question_id].question,
                times_wrong=times_wrong,
                selected_options=[
                    SelectedOption(text=text, correct=correct, count=count)
                    for (text, correct), count in tallies.wrong_selected_counts[
                        (user_id, form_id, question_id)
                    ].items()
                ],
                correct_option_texts=questions.correct_option_texts[question_id],
            )
        )
    for per_quiz in wrong_answers_by_user_quiz.values():
        for wrong_answer_list in per_quiz.values():
            wrong_answer_list.sort(key=lambda wa: wa.question_number)
    return wrong_answers_by_user_quiz


def build_confusion_block(
    form_id: UUID,
    questions: QuestionIndex,
    tallies: QuizTallies,
    distractors_by_question: dict[UUID, list[tuple[str, int]]],
) -> ConfusionBlock:
    """The most-missed questions in one quiz, worst error rate first.

    `shown` caps the list at CONFUSIONS_PER_QUIZ_MAX while `total` keeps the
    full candidate count, so the page can say how many it left out.
    """
    candidates: list[tuple[float, FormQuestion, int, int]] = []
    for question in questions.by_form.get(form_id, []):
        if question.type in FREE_TEXT_QUESTION_TYPES:
            continue
        wrong = tallies.wrong_counts_first.get(question.id, 0)
        if wrong == 0:
            continue
        respondents = tallies.respondent_counts.get(question.id, 0)
        error_rate = wrong / respondents if respondents else 0.0
        candidates.append((error_rate, question, wrong, respondents))
    # Keyed on the error rate alone: sort is stable, so questions tying on rate
    # keep their question order, and the FormQuestion itself is never compared.
    candidates.sort(key=lambda candidate: candidate[0], reverse=True)
    shown_candidates = candidates[:CONFUSIONS_PER_QUIZ_MAX]

    confusion_questions = []
    for _, question, wrong, respondents in shown_candidates:
        show_percentage = respondents >= MIN_RESPONDENTS_FOR_PERCENTAGE
        confusion_questions.append(
            QuizConfusion(
                question_number=questions.number_by_id[question.id],
                question_text=question.question,
                respondent_count=respondents,
                wrong_count=wrong,
                show_percentage=show_percentage,
                wrong_percentage=round(wrong / respondents * 100)
                if show_percentage
                else None,
                distractors=distractors_by_question.get(question.id, []),
                correct_option_texts=questions.correct_option_texts[question.id],
            )
        )
    return ConfusionBlock(
        questions=confusion_questions,
        shown=len(confusion_questions),
        total=len(candidates),
    )


def build_confusions_by_quiz(
    quiz_form_ids: set[UUID],
    questions: QuestionIndex,
    tallies: QuizTallies,
    distractors_by_question: dict[UUID, list[tuple[str, int]]],
) -> dict[UUID, ConfusionBlock]:
    return {
        form_id: build_confusion_block(
            form_id, questions, tallies, distractors_by_question
        )
        for form_id in quiz_form_ids
    }


def _build_quiz_columns(items: list[Topic | Form]) -> list[QuizColumn]:
    """One column per quiz in the course, in the order the course lists them."""
    quiz_forms = [
        item
        for item in items
        if isinstance(item, Form) and item.strategy == FormStrategy.QUIZ
    ]
    abbreviations = _unique_abbreviations([form.title for form in quiz_forms])
    return [
        QuizColumn(
            form_id=form.id,
            title=form.title,
            abbreviation=abbreviation,
            pass_percentage=form.quiz_pass_percentage,
        )
        for form, abbreviation in zip(quiz_forms, abbreviations, strict=True)
    ]


def _build_learner_row(
    user_id: int,
    items: list[Topic | Form],
    quiz_columns: list[QuizColumn],
    roster: CohortRoster,
    catalogue: CourseCatalogue,
    progress: ProgressIndex,
) -> LearnerRow:
    completed_count, total_count = _completion_counts(items, user_id, progress)
    last_title, last_at = _latest_completion(items, user_id, progress)
    quiz_cells: dict[UUID, QuizResult | None] = {
        column.form_id: _quiz_result_for(
            user_id, catalogue.forms_by_id[column.form_id], progress.forms
        )
        for column in quiz_columns
    }
    return LearnerRow(
        user_id=user_id,
        full_name=roster.learners_by_id[user_id].display_name,
        completion_percentage=_completion_percentage(completed_count, total_count),
        completed_item_count=completed_count,
        total_item_count=total_count,
        last_completed_title=last_title,
        last_completed_at=last_at,
        quiz_cells=quiz_cells,
    )


def _build_summary_tables(
    quiz_columns: list[QuizColumn], learner_rows: list[LearnerRow], max_columns: int
) -> list[SummaryTable]:
    """The course's learner rows, re-cut into page-width tables of quiz columns."""
    return [
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
                for row in learner_rows
            ],
            continued=index > 0,
        )
        for index, chunk in enumerate(_chunk_quiz_columns(quiz_columns, max_columns))
    ]


def _build_course_section(
    reg: CohortCourseRegistration,
    roster: CohortRoster,
    catalogue: CourseCatalogue,
    progress: ProgressIndex,
    confusions_by_quiz: dict[UUID, ConfusionBlock],
    max_quiz_columns: int,
) -> CourseSection:
    course = reg.collection
    items = catalogue.course_items[reg.collection_id]
    quiz_columns = _build_quiz_columns(items)
    learner_rows = [
        _build_learner_row(user_id, items, quiz_columns, roster, catalogue, progress)
        for user_id in roster.learner_ids
    ]
    return CourseSection(
        course_id=course.id,
        title=course.title,
        is_active=reg.is_active,
        item_count=len(items),
        quizzes=quiz_columns,
        learner_rows=learner_rows,
        summary_tables=_build_summary_tables(
            quiz_columns, learner_rows, max_quiz_columns
        ),
        confusions_by_quiz={
            column.form_id: confusions_by_quiz.get(
                column.form_id, ConfusionBlock(questions=[], shown=0, total=0)
            )
            for column in quiz_columns
        },
    )


def _evaluate_at_risk_flags(detail: LearnerDetail) -> list[AtRiskFlag]:
    """Every at-risk rule's verdict on one learner, from a single registry pass.

    Flags are evaluated exactly once per learner, here. The attention list
    filters and sorts these same LearnerDetail objects — it never re-evaluates,
    so a learner's flags read identically everywhere in the report.
    """
    # LearnerDetailLike is a structural stand-in (freedom_ls/reports/at_risk.py);
    # LearnerDetail satisfies it in practice but mypy can't confirm list
    # invariance and frozen-dataclass read-only attributes against a
    # Protocol declared with plain mutable fields, hence the cast.
    detail_for_rules = cast("LearnerDetailLike", detail)
    return [
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


def _build_learner_detail(
    user_id: int,
    roster: CohortRoster,
    catalogue: CourseCatalogue,
    progress: ProgressIndex,
    wrong_answers_by_user_quiz: dict[int, dict[UUID, list[WrongAnswer]]],
    now: datetime,
) -> LearnerDetail:
    user = roster.learners_by_id[user_id]
    all_items = catalogue.all_items
    completed_count, total_count = _completion_counts(all_items, user_id, progress)
    last_title, last_at = _latest_completion(all_items, user_id, progress)
    completed_items = _completed_items(all_items, user_id, progress)
    quiz_results = [
        result
        for result in (
            _quiz_result_for(user_id, form, progress.forms)
            for form_id, form in catalogue.forms_by_id.items()
            if form_id in catalogue.quiz_form_ids
        )
        if result is not None
    ]

    wrong_answers_for_user = wrong_answers_by_user_quiz.get(user_id, {})
    wrong_answers = [
        QuizWrongAnswers(
            form_id=form_id,
            title=catalogue.forms_by_id[form_id].title,
            answers=wrong_answers_for_user[form_id],
        )
        for form_id in catalogue.ordered_quiz_form_ids
        if form_id in wrong_answers_for_user
    ]

    detail = LearnerDetail(
        user_id=user_id,
        full_name=user.display_name,
        sort_key=roster.sort_key_by_id[user_id],
        completion_percentage=_completion_percentage(completed_count, total_count),
        completed_item_count=completed_count,
        total_item_count=total_count,
        last_completed_title=last_title,
        last_completed_at=last_at,
        has_any_progress=user_id in progress.user_ids_with_any_progress,
        completed_items=completed_items,
        quiz_results=quiz_results,
        wrong_answers=wrong_answers,
        report_generated_at=now,
        flags=[],
    )
    return dataclasses.replace(detail, flags=_evaluate_at_risk_flags(detail))


def _build_attention_list(learner_details: list[LearnerDetail]) -> AttentionList:
    """The flagged learners the report leads with, least-complete first."""
    flagged = sorted(
        (detail for detail in learner_details if detail.flags),
        key=lambda detail: detail.completion_percentage,
    )
    shown_flagged = flagged[:ATTENTION_LIST_MAX]
    return AttentionList(
        learners=shown_flagged, shown=len(shown_flagged), total=len(flagged)
    )


def _completion_statistics(learner_details: list[LearnerDetail]) -> CompletionStats:
    completion_values = [detail.completion_percentage for detail in learner_details]
    return CompletionStats(
        median_completion=round(statistics.median(completion_values))
        if completion_values
        else 0,
        not_started_count=sum(1 for value in completion_values if value == 0),
        complete_count=sum(1 for value in completion_values if value == 100),
    )


def gather_cohort_report_data(
    cohort_id: str, site_id: int, *, requested_by_name: str = ""
) -> CohortReportData:
    """Assemble one cohort's report data with a fixed number of batched queries.

    No query runs inside a per-learner or per-question loop — every id list is
    collected up front and every downstream lookup reads from an in-memory map
    built from a batched queryset. Each loader below runs once, in this order,
    so the query total is fixed by the cohort's course structure and never by
    how many learners or questions it has.
    """
    now = timezone.now()

    cohort = load_cohort(cohort_id, site_id)
    registrations = load_registrations(cohort, site_id)
    # Before the per-course traversals in the catalogue below, so an oversized
    # cohort is refused without paying for them.
    roster = load_roster(cohort, site_id)
    catalogue = build_course_catalogue(registrations)

    progress = load_progress_index(site_id, roster.learner_ids, catalogue)
    first_attempt_ids = load_first_attempt_ids(
        site_id, roster.learner_ids, catalogue.quiz_form_ids
    )
    questions = build_question_index(
        *load_quiz_questions(site_id, catalogue.quiz_form_ids)
    )
    sat = build_sat_questions(
        questions,
        progress.forms,
        load_selected_options_by_pair(
            site_id, progress.forms.completed_attempt_ids, questions.question_ids
        ),
    )
    distractors_by_question = index_distractors(
        load_distractor_rows(site_id, questions.question_ids, first_attempt_ids),
        questions,
    )

    tallies = tally_quiz_answers(sat, progress.forms, first_attempt_ids)
    wrong_answers_by_user_quiz = build_wrong_answers_by_user_quiz(tallies, questions)
    confusions_by_quiz = build_confusions_by_quiz(
        catalogue.quiz_form_ids, questions, tallies, distractors_by_question
    )

    course_sections = [
        _build_course_section(
            reg,
            roster,
            catalogue,
            progress,
            confusions_by_quiz,
            config.REPORTS_MAX_QUIZ_COLUMNS,
        )
        for reg in registrations
    ]
    learner_details = [
        _build_learner_detail(
            user_id, roster, catalogue, progress, wrong_answers_by_user_quiz, now
        )
        for user_id in roster.learner_ids
    ]
    stats = _completion_statistics(learner_details)

    return CohortReportData(
        cohort_name=cohort.name,
        organisation=OrganisationBrand(
            name=cohort.organisation.name,
            logo_data_uri=load_organisation_logo_data_uri(cohort.organisation),
            wordmark_size_class=_wordmark_size_class(cohort.organisation.name),
            wordmark_name=_truncate_to_budget(
                cohort.organisation.name, WORDMARK_CONDENSED_MAX_CHARS
            ),
            footer_name=_truncate_to_budget(
                cohort.organisation.name, FOOTER_ORGANISATION_MAX_CHARS
            ),
        ),
        site_name=resolve_site_name(site_id),
        show_powered_by=not cohort.organisation.is_default,
        generated_at=now,
        requested_by_name=requested_by_name,
        courses=course_sections,
        learners=learner_details,
        attention_list=_build_attention_list(learner_details),
        cohort_size=len(roster.learner_ids),
        median_completion=stats.median_completion,
        not_started_count=stats.not_started_count,
        complete_count=stats.complete_count,
    )
