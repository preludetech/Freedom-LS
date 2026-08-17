"""Tests for the at-risk rules (freedom_ls.reports.at_risk)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

import time_machine

from django.utils import timezone

from freedom_ls.reports.at_risk import (
    AT_RISK_RULES,
    FailedLatestQuizAttemptRule,
    InactiveForDaysRule,
    NoRecordedActivityRule,
)


@dataclass
class _QuizResult:
    completed_at: datetime | None
    passed: bool | None


@dataclass
class _Student:
    """A minimal stand-in for the future gather.StudentDetail, built by hand.

    Only carries the fields the base at-risk rules read.
    """

    has_any_progress: bool = True
    last_completed_at: datetime | None = None
    report_generated_at: datetime = field(default_factory=timezone.now)
    quiz_results: list[_QuizResult] = field(default_factory=list)


class TestNoRecordedActivityRule:
    def test_flags_student_with_no_progress(self) -> None:
        student = _Student(has_any_progress=False)

        reason = NoRecordedActivityRule().evaluate(student)

        assert reason == "Has not started any course item."

    def test_silent_for_student_with_progress(self) -> None:
        student = _Student(has_any_progress=True)

        reason = NoRecordedActivityRule().evaluate(student)

        assert reason is None


class TestFailedLatestQuizAttemptRule:
    def test_silent_when_no_quiz_results(self) -> None:
        student = _Student(quiz_results=[])

        reason = FailedLatestQuizAttemptRule().evaluate(student)

        assert reason is None

    def test_silent_when_latest_attempt_passed(self) -> None:
        now = timezone.now()
        student = _Student(quiz_results=[_QuizResult(completed_at=now, passed=True)])

        reason = FailedLatestQuizAttemptRule().evaluate(student)

        assert reason is None

    def test_flags_when_latest_attempt_failed(self) -> None:
        now = timezone.now()
        student = _Student(quiz_results=[_QuizResult(completed_at=now, passed=False)])

        reason = FailedLatestQuizAttemptRule().evaluate(student)

        assert reason == "Failed their most recent quiz attempt."

    def test_silent_when_latest_attempt_has_no_pass_mark(self) -> None:
        now = timezone.now()
        student = _Student(quiz_results=[_QuizResult(completed_at=now, passed=None)])

        reason = FailedLatestQuizAttemptRule().evaluate(student)

        assert reason is None

    def test_judges_only_the_most_recent_attempt_by_completion_time(self) -> None:
        earlier = timezone.now()
        later = earlier + timedelta(hours=1)
        student = _Student(
            quiz_results=[
                _QuizResult(completed_at=later, passed=True),
                _QuizResult(completed_at=earlier, passed=False),
            ]
        )

        reason = FailedLatestQuizAttemptRule().evaluate(student)

        assert reason is None


class TestInactiveForDaysRule:
    def test_silent_when_student_has_no_completions_at_all(self) -> None:
        student = _Student(last_completed_at=None)

        reason = InactiveForDaysRule(days=7).evaluate(student)

        assert reason is None

    def test_silent_at_exactly_the_threshold(self) -> None:
        with time_machine.travel("2026-01-01T00:00:00Z", tick=False):
            last_completed_at = timezone.now()
        with time_machine.travel("2026-01-08T00:00:00Z", tick=False):
            now = timezone.now()
        student = _Student(last_completed_at=last_completed_at, report_generated_at=now)

        reason = InactiveForDaysRule(days=7).evaluate(student)

        assert reason is None

    def test_flags_one_day_past_the_threshold(self) -> None:
        with time_machine.travel("2026-01-01T00:00:00Z", tick=False):
            last_completed_at = timezone.now()
        with time_machine.travel("2026-01-09T00:00:00Z", tick=False):
            now = timezone.now()
        student = _Student(last_completed_at=last_completed_at, report_generated_at=now)

        reason = InactiveForDaysRule(days=7).evaluate(student)

        assert reason == "No activity recorded in over 7 days."

    def test_threshold_is_a_constructor_parameter(self) -> None:
        with time_machine.travel("2026-01-01T00:00:00Z", tick=False):
            last_completed_at = timezone.now()
        with time_machine.travel("2026-01-05T00:00:00Z", tick=False):
            now = timezone.now()
        student = _Student(last_completed_at=last_completed_at, report_generated_at=now)

        reason = InactiveForDaysRule(days=3).evaluate(student)

        assert reason == "No activity recorded in over 3 days."


class TestAtRiskRules:
    def test_a_student_can_trip_more_than_one_rule(self) -> None:
        with time_machine.travel("2026-01-01T00:00:00Z", tick=False):
            last_completed_at = timezone.now()
        with time_machine.travel("2026-01-09T00:00:00Z", tick=False):
            now = timezone.now()
        student = _Student(
            has_any_progress=True,
            last_completed_at=last_completed_at,
            report_generated_at=now,
            quiz_results=[_QuizResult(completed_at=last_completed_at, passed=False)],
        )

        reasons = {rule.id: rule.evaluate(student) for rule in AT_RISK_RULES}
        tripped = {rule_id for rule_id, reason in reasons.items() if reason is not None}

        assert tripped == {"failed_latest_quiz", "inactive"}
