"""Tests for freedom_ls.reports.views (the generate and download admin views)."""

from __future__ import annotations

import pytest
from guardian.shortcuts import assign_perm

from django.core.files.base import ContentFile
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.reports.factories import GeneratedReportFactory
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.student_management.factories import CohortFactory

pytestmark = pytest.mark.django_db


def _generate_url() -> str:
    return reverse("admin:freedom_ls_reports_generatedreport_generate")


def _download_url(report_pk: object) -> str:
    return reverse(
        "admin:freedom_ls_reports_generatedreport_download", args=[report_pk]
    )


def _staff_user_with_cohort_view_permission(cohort: object) -> object:
    user = UserFactory(is_staff=True)
    assign_perm("freedom_ls_student_management.view_cohort", user, cohort)
    return user


def _save_ready_file(report: GeneratedReport) -> None:
    report.file.save(
        "cohort-report.pdf", ContentFile(b"%PDF-1.4 test bytes"), save=True
    )


class TestGenerateReportViewGet:
    def test_renders_cohorts_the_user_can_see(
        self, mock_site_context: object, client: object
    ) -> None:
        cohort = CohortFactory(name="Alpha Cohort")
        user = _staff_user_with_cohort_view_permission(cohort)
        client.force_login(user)

        response = client.get(_generate_url())

        assert response.status_code == 200
        assert "Alpha Cohort" in response.content.decode()


class TestGenerateReportViewPost:
    def test_user_without_view_cohort_permission_gets_404_and_creates_no_row(
        self, mock_site_context: object, client: object
    ) -> None:
        cohort = CohortFactory()
        user = UserFactory(is_staff=True)
        client.force_login(user)

        response = client.post(_generate_url(), data={"cohort": str(cohort.pk)})

        assert response.status_code == 404
        assert GeneratedReport.objects.filter(cohort=cohort).count() == 0

    def test_user_with_permission_creates_pending_report(
        self, mock_site_context: object, client: object
    ) -> None:
        cohort = CohortFactory()
        user = _staff_user_with_cohort_view_permission(cohort)
        client.force_login(user)

        client.post(_generate_url(), data={"cohort": str(cohort.pk)})

        report = GeneratedReport.objects.get(cohort=cohort)
        assert report.status == GeneratedReport.STATUS_PENDING

    def test_created_report_uses_the_cohorts_site_id(
        self, mock_site_context: object, client: object
    ) -> None:
        cohort = CohortFactory()
        user = _staff_user_with_cohort_view_permission(cohort)
        client.force_login(user)

        client.post(_generate_url(), data={"cohort": str(cohort.pk)})

        report = GeneratedReport.objects.get(cohort=cohort)
        assert report.site_id == cohort.site_id

    def test_two_simultaneous_creates_produce_exactly_one_report(
        self, mock_site_context: object, client: object, mocker: object
    ) -> None:
        """Exercises the partial unique index's IntegrityError guard directly,
        bypassing the view's friendly pre-check so the real DB constraint --
        not the pre-check -- is what is under test."""
        cohort = CohortFactory()
        user = _staff_user_with_cohort_view_permission(cohort)
        client.force_login(user)
        mocker.patch(
            "freedom_ls.reports.views._has_inflight_report", return_value=False
        )

        client.post(_generate_url(), data={"cohort": str(cohort.pk)})
        client.post(_generate_url(), data={"cohort": str(cohort.pk)})

        assert GeneratedReport.objects.filter(cohort=cohort).count() == 1


class TestDownloadReportView:
    def test_user_without_view_cohort_permission_gets_403(
        self, mock_site_context: object, client: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_READY
        )
        _save_ready_file(report)
        user = UserFactory(is_staff=True)
        client.force_login(user)

        response = client.get(_download_url(report.pk))

        assert response.status_code == 403

    def test_anonymous_user_redirected_to_admin_login(
        self, mock_site_context: object, client: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_READY
        )

        response = client.get(_download_url(report.pk))

        assert response.status_code == 302
        assert "/login" in response.url

    def test_pending_report_404s(
        self, mock_site_context: object, client: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )
        user = _staff_user_with_cohort_view_permission(cohort)
        client.force_login(user)

        response = client.get(_download_url(report.pk))

        assert response.status_code == 404

    def test_ready_report_is_downloadable_attachment(
        self, mock_site_context: object, client: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_READY
        )
        _save_ready_file(report)
        user = _staff_user_with_cohort_view_permission(cohort)
        client.force_login(user)

        response = client.get(_download_url(report.pk))

        assert response.status_code == 200
        assert response["Content-Disposition"].startswith("attachment;")

    def test_ready_report_response_carries_no_store_cache_header(
        self, mock_site_context: object, client: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_READY
        )
        _save_ready_file(report)
        user = _staff_user_with_cohort_view_permission(cohort)
        client.force_login(user)

        response = client.get(_download_url(report.pk))

        # admin_view() layers its own never_cache directives on top of ours,
        # so assert the directive we set is present rather than an exact
        # match against the merged header.
        assert "no-store" in response["Cache-Control"]

    def test_row_with_missing_storage_file_404s(
        self, mock_site_context: object, client: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_READY
        )
        _save_ready_file(report)
        report.file.storage.delete(report.file.name)
        user = _staff_user_with_cohort_view_permission(cohort)
        client.force_login(user)

        response = client.get(_download_url(report.pk))

        assert response.status_code == 404
