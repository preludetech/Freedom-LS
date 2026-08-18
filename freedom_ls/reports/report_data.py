"""The cohort report's output contract: the frozen tree the render layer walks.

Nothing here touches the ORM. `freedom_ls.reports.indexes` runs the queries and
`freedom_ls.reports.gather` assembles these dataclasses from what it loads; the
render layer walks the result and never queries. Keeping the contract in its own
module is what lets the render layer and its tests depend on the shape without
pulling in the query layer.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from uuid import UUID

ATTENTION_LIST_MAX = 12
CONFUSIONS_PER_QUIZ_MAX = 10
MIN_RESPONDENTS_FOR_PERCENTAGE = 10


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
    # the threshold invariant in one place (the confusion block builder) rather
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
    # organisation identity FLS records.
    site_name: str
    generated_at: datetime
    requested_by_name: str
    courses: list[CourseSection]
    students: list[StudentDetail]
    attention_list: AttentionList
    cohort_size: int
    median_completion: int
    not_started_count: int
    complete_count: int
