"""Tests for the GeneratedReport model."""

from __future__ import annotations

import pytest

from django.core.files.base import ContentFile
from django.db import IntegrityError

from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.reports.factories import GeneratedReportFactory
from freedom_ls.reports.models import GeneratedReport, report_upload_path


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

        assert path == f"cohort_reports/{report.pk}-cohort-report.pdf"

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

    def test_str_names_the_organisation(self, mock_site_context: object) -> None:
        """Cohort names are unique per organisation, not per site, so the
        name alone no longer identifies what is about to be destroyed."""
        organisation = OrganisationFactory(name="Northside College")
        report = GeneratedReportFactory(
            cohort=CohortFactory(name="Alpha Cohort", organisation=organisation)
        )

        assert "Northside College" in str(report)


# Deletion hygiene: report files never outlive their row.
@pytest.mark.django_db
class TestDeletionHygiene:
    def test_deleting_report_through_orm_removes_its_file(
        self, mock_site_context: object
    ) -> None:
        report = GeneratedReportFactory()
        report.file.save("cohort-report.pdf", ContentFile(b"%PDF-1.4"), save=True)
        storage = report.file.storage
        file_name = report.file.name

        report.delete()

        assert storage.exists(file_name) is False

    def test_deleting_via_queryset_delete_removes_files(
        self, mock_site_context: object
    ) -> None:
        report = GeneratedReportFactory()
        report.file.save("cohort-report.pdf", ContentFile(b"%PDF-1.4"), save=True)
        storage = report.file.storage
        file_name = report.file.name

        GeneratedReport.objects.filter(pk=report.pk).delete()

        assert storage.exists(file_name) is False

    def test_deleting_cohort_removes_report_rows_and_files(
        self, mock_site_context: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(cohort=cohort)
        report.file.save("cohort-report.pdf", ContentFile(b"%PDF-1.4"), save=True)
        storage = report.file.storage
        file_name = report.file.name
        report_pk = report.pk

        cohort.delete()

        assert GeneratedReport.objects.filter(pk=report_pk).exists() is False
        assert storage.exists(file_name) is False

    def test_other_reports_survive_deletion(self, mock_site_context: object) -> None:
        """Every report shares one directory, so only the row's own file goes."""
        kept = GeneratedReportFactory()
        kept.file.save("cohort-report.pdf", ContentFile(b"%PDF-1.4"), save=True)
        deleted = GeneratedReportFactory()
        deleted.file.save("cohort-report.pdf", ContentFile(b"%PDF-1.4"), save=True)
        storage = deleted.file.storage

        deleted.delete()

        assert storage.exists("cohort_reports") is True
        assert storage.exists(kept.file.name) is True

    def test_deleting_a_report_without_a_file_is_a_no_op(
        self, mock_site_context: object
    ) -> None:
        report = GeneratedReportFactory()

        report.delete()

        assert GeneratedReport.objects.filter(pk=report.pk).exists() is False
