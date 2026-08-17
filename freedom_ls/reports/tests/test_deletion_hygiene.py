"""Tests for deletion hygiene: report files never outlive their row."""

from __future__ import annotations

import pytest

from django.core.files.base import ContentFile

from freedom_ls.reports.factories import GeneratedReportFactory
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.student_management.factories import CohortFactory


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

        assert storage.exists("reports") is True
        assert storage.exists(kept.file.name) is True

    def test_deleting_a_report_without_a_file_is_a_no_op(
        self, mock_site_context: object
    ) -> None:
        report = GeneratedReportFactory()

        report.delete()

        assert GeneratedReport.objects.filter(pk=report.pk).exists() is False
