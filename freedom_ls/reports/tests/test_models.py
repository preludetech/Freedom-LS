"""Tests for the GeneratedReport model."""

from __future__ import annotations

import pytest

from django.db import IntegrityError

from freedom_ls.reports.factories import GeneratedReportFactory
from freedom_ls.reports.models import GeneratedReport, report_upload_path
from freedom_ls.student_management.factories import CohortFactory


@pytest.mark.django_db
class TestOneInflightReportPerCohortConstraint:
    def test_second_pending_report_for_same_cohort_raises_integrity_error(
        self, mock_site_context: object
    ) -> None:
        cohort = CohortFactory()
        GeneratedReportFactory(cohort=cohort, status=GeneratedReport.STATUS_PENDING)

        with pytest.raises(IntegrityError):
            GeneratedReportFactory(cohort=cohort, status=GeneratedReport.STATUS_PENDING)

    def test_second_running_report_for_same_cohort_raises_integrity_error(
        self, mock_site_context: object
    ) -> None:
        cohort = CohortFactory()
        GeneratedReportFactory(cohort=cohort, status=GeneratedReport.STATUS_RUNNING)

        with pytest.raises(IntegrityError):
            GeneratedReportFactory(cohort=cohort, status=GeneratedReport.STATUS_PENDING)

    def test_pending_report_after_a_ready_report_succeeds(
        self, mock_site_context: object
    ) -> None:
        cohort = CohortFactory()
        GeneratedReportFactory(cohort=cohort, status=GeneratedReport.STATUS_READY)

        second = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )

        assert second.pk is not None

    def test_pending_report_after_a_failed_report_succeeds(
        self, mock_site_context: object
    ) -> None:
        cohort = CohortFactory()
        GeneratedReportFactory(cohort=cohort, status=GeneratedReport.STATUS_FAILED)

        second = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )

        assert second.pk is not None


@pytest.mark.django_db
class TestReportUploadPath:
    def test_upload_path_is_pk_derived(self, mock_site_context: object) -> None:
        report = GeneratedReportFactory()

        path = report_upload_path(report, "cohort-report.pdf")

        assert path == f"reports/{report.pk}/cohort-report.pdf"

    def test_upload_path_never_contains_cohort_name(
        self, mock_site_context: object
    ) -> None:
        cohort = CohortFactory(name="Very Secret Cohort Name")
        report = GeneratedReportFactory(cohort=cohort)

        path = report_upload_path(report, "cohort-report.pdf")

        assert "Very Secret Cohort Name" not in path

    def test_upload_path_raises_when_pk_is_unset(self) -> None:
        # The UUID pk field defaults to a fresh uuid4 on construction, so an
        # explicit id=None is the only way to observe the "unsaved" guard.
        unsaved = GeneratedReport(id=None)

        with pytest.raises(ValueError, match="saved"):
            report_upload_path(unsaved, "cohort-report.pdf")


@pytest.mark.django_db
class TestGeneratedReportStr:
    """The delete-confirmation screens are the only place an admin can check
    what is about to be destroyed, and they show nothing but this string."""

    def test_str_names_the_cohort(self, mock_site_context: object) -> None:
        cohort = CohortFactory(name="Alpha Cohort")
        report = GeneratedReportFactory(cohort=cohort)

        assert "Alpha Cohort" in str(report)

    def test_str_does_not_expose_the_cohort_uuid(
        self, mock_site_context: object
    ) -> None:
        report = GeneratedReportFactory(cohort=CohortFactory(name="Alpha Cohort"))

        assert str(report.cohort_id) not in str(report)

    def test_str_keeps_the_status(self, mock_site_context: object) -> None:
        report = GeneratedReportFactory(status=GeneratedReport.STATUS_READY)

        assert GeneratedReport.STATUS_READY in str(report)
