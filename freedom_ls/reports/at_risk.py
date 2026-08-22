"""At-risk rule protocol and the rule set the cohort report evaluates.

A rule is a small object: a stable `id`, a human-readable `label`, a
`severity`, and an `evaluate(learner)` method returning a reason string or
None. Adding, removing or reordering a rule is a one-line change to
AT_RISK_RULES at the foot of this module, and needs no edit to the gathering
or rendering code.

`LearnerDetailLike` is a structural stand-in for the real per-learner report
row, `freedom_ls.reports.gather.LearnerDetail`. It carries only the fields the
rules below actually read. Because `typing.Protocol` is duck-typed, the real
dataclass needs no inheritance from it — it only needs to expose the same
attributes. `report_generated_at` is the single instant the whole report (and
therefore every rule) is evaluated against, so two rules can never disagree
about what "now" was.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol


class QuizResultLike(Protocol):
    """The subset of a per-quiz outcome the base rules read."""

    completed_at: datetime | None
    passed: bool | None


class LearnerDetailLike(Protocol):
    """The subset of a per-learner report row the base rules read."""

    has_any_progress: bool
    last_completed_at: datetime | None
    report_generated_at: datetime
    quiz_results: list[QuizResultLike]


class AtRiskRule(Protocol):
    """A single at-risk check: identity, display label, severity, evaluator."""

    id: str
    label: str
    severity: str

    def evaluate(self, learner: LearnerDetailLike) -> str | None: ...


# How heavily the report draws a rule's flags: a role token name, so a badge
# is coloured by the theme rather than by this module.
SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"


class NoRecordedActivityRule:
    id = "no_activity"
    label = "No recorded activity"
    severity = SEVERITY_ERROR

    def evaluate(self, learner: LearnerDetailLike) -> str | None:
        if learner.has_any_progress:
            return None
        return "Has not started any course item."


class FailedLatestQuizAttemptRule:
    id = "failed_latest_quiz"
    label = "Failed most recent quiz attempt"
    severity = SEVERITY_ERROR

    def evaluate(self, learner: LearnerDetailLike) -> str | None:
        latest: QuizResultLike | None = None
        latest_completed_at: datetime | None = None
        for result in learner.quiz_results:
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
    severity = SEVERITY_WARNING

    def __init__(self, days: int = 7) -> None:
        self.days = days

    def evaluate(self, learner: LearnerDetailLike) -> str | None:
        # A learner with no completions at all is NoRecordedActivityRule's
        # concern, not this one.
        if learner.last_completed_at is None:
            return None
        elapsed = learner.report_generated_at - learner.last_completed_at
        if elapsed <= timedelta(days=self.days):
            return None
        return f"No activity recorded in over {self.days} days."


AT_RISK_RULES: list[AtRiskRule] = [
    NoRecordedActivityRule(),
    FailedLatestQuizAttemptRule(),
    InactiveForDaysRule(days=7),
]
