"""At-risk rule protocol and the base (v1) rule set.

A rule is a small object: a stable `id`, a human-readable `label`, and an
`evaluate(student)` method returning a reason string or None. Downstream
projects extend the registry (see `at_risk/loader.py`) by exporting their own
`AT_RISK_RULES = [*BASE_AT_RISK_RULES, MyRule(...)]` list — adding a rule is a
one-line change to a list, never an edit to this module.

`StudentDetailLike` is a structural stand-in for the real per-student report
row (`freedom_ls.reports.gather.StudentDetail`), which is defined in a later
implementation batch and does not exist yet. It carries only the fields the
base rules below actually read. Because `typing.Protocol` is duck-typed, the
real dataclass needs no inheritance from it — it only needs to expose the
same attributes. See this module's implementation notes for the field the
real dataclass must add: `report_generated_at`, the single instant the whole
report (and therefore every rule) is evaluated against.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol


class QuizResultLike(Protocol):
    """The subset of a per-quiz outcome the base rules read."""

    completed_at: datetime | None
    passed: bool | None


class StudentDetailLike(Protocol):
    """The subset of a per-student report row the base rules read."""

    has_any_progress: bool
    last_completed_at: datetime | None
    report_generated_at: datetime
    quiz_results: list[QuizResultLike]


class AtRiskRule(Protocol):
    """A single at-risk check: identity, display label, and a pure evaluator."""

    id: str
    label: str

    def evaluate(self, student: StudentDetailLike) -> str | None: ...


class NoRecordedActivityRule:
    id = "no_activity"
    label = "No recorded activity"

    def evaluate(self, student: StudentDetailLike) -> str | None:
        if student.has_any_progress:
            return None
        return "Has not started any course item."


class FailedLatestQuizAttemptRule:
    id = "failed_latest_quiz"
    label = "Failed most recent quiz attempt"

    def evaluate(self, student: StudentDetailLike) -> str | None:
        latest: QuizResultLike | None = None
        latest_completed_at: datetime | None = None
        for result in student.quiz_results:
            completed_at = result.completed_at
            if completed_at is None:
                continue
            if latest_completed_at is None or completed_at > latest_completed_at:
                latest = result
                latest_completed_at = completed_at
        # A quiz with quiz_pass_percentage unset yields passed=None: no pass
        # mark, no verdict, no flag.
        if latest is not None and latest.passed is False:
            return "Failed their most recent quiz attempt."
        return None


class InactiveForDaysRule:
    id = "inactive"
    label = "No activity recently"

    def __init__(self, days: int = 7) -> None:
        self.days = days

    def evaluate(self, student: StudentDetailLike) -> str | None:
        # A student with no completions at all is NoRecordedActivityRule's
        # concern, not this one.
        if student.last_completed_at is None:
            return None
        elapsed = student.report_generated_at - student.last_completed_at
        if elapsed <= timedelta(days=self.days):
            return None
        return f"No activity recorded in over {self.days} days."


BASE_AT_RISK_RULES: list[AtRiskRule] = [
    NoRecordedActivityRule(),
    FailedLatestQuizAttemptRule(),
    InactiveForDaysRule(days=7),
]
