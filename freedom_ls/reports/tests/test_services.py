"""Tests for freedom_ls.reports.services: starting, finding and serving cohort reports."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from unittest.mock import patch

import pytest
import time_machine

from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.http import Http404

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.reports.factories import GeneratedReportFactory
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.reports.services import (
    has_inflight_report,
    latest_cohort_reports,
    report_file_response,
    request_cohort_report,
)

pytestmark = pytest.mark.django_db

type CaptureOnCommit = Callable[..., AbstractContextManager[list[Callable[[], None]]]]


@pytest.fixture(autouse=True)
def _site_context(mock_site_context):
    """Every test here builds site-aware objects."""


class TestRequestCohortReport:
    def test_creates_a_pending_row_for_the_cohort_and_requester(self) -> None:
        cohort = CohortFactory()
        user = UserFactory()

        report = request_cohort_report(cohort, user)

        assert report is not None
        assert report.status == GeneratedReport.STATUS_PENDING
        assert (report.cohort, report.requested_by) == (cohort, user)
        assert report.site_id == cohort.site_id

    def test_enqueues_the_task_once_the_transaction_commits(
        self, django_capture_on_commit_callbacks: CaptureOnCommit
    ) -> None:
        cohort = CohortFactory()

        with (
            patch("freedom_ls.reports.services.default_task_backend") as backend,
            django_capture_on_commit_callbacks(execute=True),
        ):
            report = request_cohort_report(cohort, UserFactory())

        assert report is not None
        backend.enqueue.assert_called_once()
        assert backend.enqueue.call_args.kwargs["args"] == [
            str(report.pk),
            cohort.site_id,
        ]

    def test_returns_none_while_a_report_is_in_flight(self) -> None:
        cohort = CohortFactory()
        GeneratedReportFactory(cohort=cohort, status=GeneratedReport.STATUS_RUNNING)

        assert request_cohort_report(cohort, UserFactory()) is None
        assert GeneratedReport.objects.filter(cohort=cohort).count() == 1

    def test_returns_none_when_the_insert_loses_the_race(self) -> None:
        cohort = CohortFactory()

        with patch.object(
            GeneratedReport.objects, "create", side_effect=IntegrityError
        ):
            result = request_cohort_report(cohort, UserFactory())

        assert result is None


class TestHasInflightReport:
    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            (GeneratedReport.STATUS_PENDING, True),
            (GeneratedReport.STATUS_RUNNING, True),
            (GeneratedReport.STATUS_READY, False),
            (GeneratedReport.STATUS_FAILED, False),
        ],
    )
    def test_only_pending_and_running_count(self, status: str, expected: bool) -> None:
        cohort = CohortFactory()
        GeneratedReportFactory(cohort=cohort, status=status)

        assert has_inflight_report(cohort) is expected


class TestLatestCohortReports:
    def test_returns_the_in_flight_the_newest_ready_and_nothing_else(self) -> None:
        cohort = CohortFactory()
        with time_machine.travel("2026-01-01 10:00", tick=False):
            GeneratedReportFactory(cohort=cohort, status=GeneratedReport.STATUS_READY)
        with time_machine.travel("2026-01-02 10:00", tick=False):
            newest_ready = GeneratedReportFactory(
                cohort=cohort, status=GeneratedReport.STATUS_READY
            )
        with time_machine.travel("2026-01-03 10:00", tick=False):
            running = GeneratedReportFactory(
                cohort=cohort, status=GeneratedReport.STATUS_RUNNING
            )

        state = latest_cohort_reports(cohort)

        assert state.in_flight == running
        assert state.ready == newest_ready
        assert state.failed is None

    def test_a_failure_newer_than_the_ready_report_is_returned(self) -> None:
        cohort = CohortFactory()
        with time_machine.travel("2026-01-01 10:00", tick=False):
            GeneratedReportFactory(cohort=cohort, status=GeneratedReport.STATUS_READY)
        with time_machine.travel("2026-01-02 10:00", tick=False):
            failed = GeneratedReportFactory(
                cohort=cohort, status=GeneratedReport.STATUS_FAILED
            )

        assert latest_cohort_reports(cohort).failed == failed

    def test_a_failure_older_than_the_ready_report_is_dropped(self) -> None:
        cohort = CohortFactory()
        with time_machine.travel("2026-01-01 10:00", tick=False):
            GeneratedReportFactory(cohort=cohort, status=GeneratedReport.STATUS_FAILED)
        with time_machine.travel("2026-01-02 10:00", tick=False):
            GeneratedReportFactory(cohort=cohort, status=GeneratedReport.STATUS_READY)

        assert latest_cohort_reports(cohort).failed is None

    def test_a_failure_with_no_ready_report_is_returned(self) -> None:
        cohort = CohortFactory()
        failed = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_FAILED
        )

        assert latest_cohort_reports(cohort).failed == failed

    def test_another_cohorts_reports_are_ignored(self) -> None:
        GeneratedReportFactory(status=GeneratedReport.STATUS_READY)

        state = latest_cohort_reports(CohortFactory())

        assert (state.in_flight, state.ready, state.failed) == (None, None, None)

    def test_one_query_covers_all_three_and_the_requester_is_already_loaded(
        self, django_assert_max_num_queries
    ) -> None:
        cohort = CohortFactory()
        requester = UserFactory(first_name="Reta", last_name="Quester")
        GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_READY, requested_by=requester
        )

        with django_assert_max_num_queries(1):
            state = latest_cohort_reports(cohort)
            ready = state.ready

        assert ready is not None
        assert ready.requested_by is not None
        with django_assert_max_num_queries(0):
            assert ready.requested_by.display_name == "Reta Quester"


class TestReportFileResponse:
    def test_a_ready_report_streams_as_a_private_attachment(self) -> None:
        report = GeneratedReportFactory(
            cohort=CohortFactory(name="Alpha Group"),
            status=GeneratedReport.STATUS_READY,
        )
        report.file.save("r.pdf", ContentFile(b"%PDF-1.4 x"), save=True)

        response = report_file_response(report)

        assert response["Cache-Control"] == "private, no-store, must-revalidate"
        assert response["Content-Disposition"].endswith(
            '-alpha-group-progress-report.pdf"'
        )

    def test_a_pending_report_is_a_404(self) -> None:
        report = GeneratedReportFactory(status=GeneratedReport.STATUS_PENDING)

        with pytest.raises(Http404):
            report_file_response(report)

    def test_a_ready_report_with_no_file_is_a_404(self) -> None:
        report = GeneratedReportFactory(status=GeneratedReport.STATUS_READY)

        with pytest.raises(Http404):
            report_file_response(report)
