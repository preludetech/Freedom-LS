"""Tests for the report output contract's errors."""

from __future__ import annotations

from freedom_ls.panel_framework.errors import PanelBodyTooLargeError
from freedom_ls.reports.report_data import ReportTooLargeError, over_limit_message


def test_a_report_too_large_error_is_a_panel_body_too_large_error() -> None:
    assert issubclass(ReportTooLargeError, PanelBodyTooLargeError)


def test_a_report_too_large_error_carries_the_over_limit_message_and_its_figures() -> (
    None
):
    error = ReportTooLargeError("Big", 3, 2)

    assert str(error) == over_limit_message("Big", 3, 2)
    assert (error.cohort_name, error.learner_count, error.limit) == ("Big", 3, 2)
