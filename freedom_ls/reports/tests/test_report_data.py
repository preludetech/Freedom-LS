"""Tests for the report output contract's errors."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from panel_framework.errors import PanelBodyTooLargeError

from freedom_ls.form_engine.models import CompletionReason
from freedom_ls.reports.report_data import (
    QuizAttempt,
    ReportTooLargeError,
    over_limit_message,
    over_limit_reason,
)


def test_a_report_too_large_error_is_a_panel_body_too_large_error() -> None:
    assert issubclass(ReportTooLargeError, PanelBodyTooLargeError)


def test_a_report_too_large_error_carries_the_over_limit_message_and_its_figures() -> (
    None
):
    error = ReportTooLargeError("Big", 3, 2)

    assert str(error) == over_limit_message("Big", 3, 2)
    assert (error.cohort_name, error.learner_count, error.limit) == ("Big", 3, 2)


def test_a_quiz_attempt_given_no_completion_reason_reads_as_learner_submitted() -> None:
    attempt = QuizAttempt(
        form_progress_id=uuid4(),
        attempt_number=1,
        completed_at=datetime(2030, 1, 1, tzinfo=UTC),
        score=1,
        max_score=2,
        percentage=50,
        passed=False,
    )

    assert attempt.completion_reason == CompletionReason.LEARNER_SUBMITTED.label


def test_the_over_limit_message_is_the_cohort_name_followed_by_the_reason() -> None:
    assert over_limit_message("Big", 3, 2) == f"Big {over_limit_reason(3, 2)}"
