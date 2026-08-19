"""Tests for freedom_ls.reports.tasks.generate_cohort_report."""

from __future__ import annotations

import pytest

from django.test import override_settings

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.reports.factories import GeneratedReportFactory
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.reports.render import ReportRenderError
from freedom_ls.reports.tasks import generate_cohort_report
from freedom_ls.student_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
)

pytestmark = pytest.mark.django_db

FAKE_PDF_BYTES = b"%PDF-1.4 fake report bytes"


class TestGenerateCohortReportHappyPath:
    def test_successful_generation_leaves_status_ready(
        self, mock_site_context: object, mocker: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )

        mocker.patch(
            "freedom_ls.reports.tasks.render_report_pdf", return_value=FAKE_PDF_BYTES
        )

        generate_cohort_report(str(report.pk), report.site_id)

        report.refresh_from_db()
        assert report.status == GeneratedReport.STATUS_READY

    def test_successful_generation_produces_non_empty_file(
        self, mock_site_context: object, mocker: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )

        mocker.patch(
            "freedom_ls.reports.tasks.render_report_pdf", return_value=FAKE_PDF_BYTES
        )

        generate_cohort_report(str(report.pk), report.site_id)

        report.refresh_from_db()
        assert report.file.size > 0


class TestGenerateCohortReportRequester:
    def test_report_data_carries_the_requesters_display_name(
        self, mock_site_context: object, mocker: object
    ) -> None:
        cohort = CohortFactory()
        requester = UserFactory(first_name="Ada", last_name="Lovelace")
        report = GeneratedReportFactory(
            cohort=cohort,
            requested_by=requester,
            status=GeneratedReport.STATUS_PENDING,
        )

        render = mocker.patch(
            "freedom_ls.reports.tasks.render_report_pdf", return_value=FAKE_PDF_BYTES
        )

        generate_cohort_report(str(report.pk), report.site_id)

        data = render.call_args.args[0]
        assert data.requested_by_name == "Ada Lovelace"

    def test_report_without_a_requester_still_generates(
        self, mock_site_context: object, mocker: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, requested_by=None, status=GeneratedReport.STATUS_PENDING
        )

        render = mocker.patch(
            "freedom_ls.reports.tasks.render_report_pdf", return_value=FAKE_PDF_BYTES
        )

        generate_cohort_report(str(report.pk), report.site_id)

        report.refresh_from_db()
        assert report.status == GeneratedReport.STATUS_READY
        assert render.call_args.args[0].requested_by_name == ""


class TestGenerateCohortReportRenderFailure:
    def test_render_error_leaves_status_failed(
        self, mock_site_context: object, mocker: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )

        mocker.patch(
            "freedom_ls.reports.tasks.render_report_pdf",
            side_effect=ReportRenderError("boom"),
        )

        generate_cohort_report(str(report.pk), report.site_id)

        report.refresh_from_db()
        assert report.status == GeneratedReport.STATUS_FAILED

    def test_render_error_sets_readable_error_message(
        self, mock_site_context: object, mocker: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )

        mocker.patch(
            "freedom_ls.reports.tasks.render_report_pdf",
            side_effect=ReportRenderError("could not resolve a static asset"),
        )

        generate_cohort_report(str(report.pk), report.site_id)

        report.refresh_from_db()
        assert report.error_message == "could not resolve a static asset"

    def test_render_error_sets_finished_at(
        self, mock_site_context: object, mocker: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )

        mocker.patch(
            "freedom_ls.reports.tasks.render_report_pdf",
            side_effect=ReportRenderError("boom"),
        )

        generate_cohort_report(str(report.pk), report.site_id)

        report.refresh_from_db()
        assert report.finished_at is not None

    def test_render_error_leaves_cohort_immediately_regeneratable(
        self, mock_site_context: object, mocker: object
    ) -> None:
        """A failed report does not hold the partial unique index open."""
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )

        mocker.patch(
            "freedom_ls.reports.tasks.render_report_pdf",
            side_effect=ReportRenderError("boom"),
        )

        generate_cohort_report(str(report.pk), report.site_id)

        second = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )

        assert second.pk is not None


class TestGenerateCohortReportTooLarge:
    def test_cohort_over_max_students_leaves_status_failed(
        self, mock_site_context: object
    ) -> None:
        cohort = CohortFactory()
        CohortMembershipFactory(cohort=cohort)
        CohortMembershipFactory(cohort=cohort)
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )

        with override_settings(REPORTS_MAX_STUDENTS=1):
            generate_cohort_report(str(report.pk), report.site_id)

        report.refresh_from_db()
        assert report.status == GeneratedReport.STATUS_FAILED

    def test_cohort_over_max_students_error_message_names_the_limit(
        self, mock_site_context: object
    ) -> None:
        cohort = CohortFactory()
        CohortMembershipFactory(cohort=cohort)
        CohortMembershipFactory(cohort=cohort)
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )

        with override_settings(REPORTS_MAX_STUDENTS=1):
            generate_cohort_report(str(report.pk), report.site_id)

        report.refresh_from_db()
        assert "1" in report.error_message


class TestGenerateCohortReportUnexpectedException:
    def test_unexpected_exception_type_leaves_status_failed(
        self, mock_site_context: object, mocker: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )

        mocker.patch(
            "freedom_ls.reports.tasks.gather_cohort_report_data",
            side_effect=TypeError("boom"),
        )

        with pytest.raises(TypeError):
            generate_cohort_report(str(report.pk), report.site_id)

        report.refresh_from_db()
        assert report.status == GeneratedReport.STATUS_FAILED

    def test_unexpected_exception_still_propagates(
        self, mock_site_context: object, mocker: object
    ) -> None:
        """The worker's own error reporting must still see the exception."""
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )

        mocker.patch(
            "freedom_ls.reports.tasks.gather_cohort_report_data",
            side_effect=TypeError("boom"),
        )

        with pytest.raises(TypeError, match="boom"):
            generate_cohort_report(str(report.pk), report.site_id)


class TestGenerateCohortReportSiteFiltering:
    def test_task_does_nothing_for_report_on_another_site(
        self, mock_site_context: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )
        other_site = SiteFactory()

        generate_cohort_report(str(report.pk), other_site.pk)

        report.refresh_from_db()
        assert report.status == GeneratedReport.STATUS_PENDING
