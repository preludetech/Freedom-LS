"""Tests for freedom_ls.reports.admin.GeneratedReportAdmin."""

from __future__ import annotations

import pytest

from django.core.files.base import ContentFile
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.reports.factories import GeneratedReportFactory
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.student_management.factories import CohortFactory

pytestmark = pytest.mark.django_db


def _changelist_url() -> str:
    return reverse("admin:freedom_ls_reports_generatedreport_changelist")


def _add_url() -> str:
    return reverse("admin:freedom_ls_reports_generatedreport_add")


def _change_url(report_pk: object) -> str:
    return reverse("admin:freedom_ls_reports_generatedreport_change", args=[report_pk])


def _download_url(report_pk: object) -> str:
    return reverse(
        "admin:freedom_ls_reports_generatedreport_download", args=[report_pk]
    )


def _superuser() -> object:
    return UserFactory(is_staff=True, is_superuser=True)


class TestGeneratedReportAdminChangelist:
    def test_changelist_renders_for_staff_user(
        self, mock_site_context: object, client: object
    ) -> None:
        user = _superuser()
        client.force_login(user)

        response = client.get(_changelist_url())

        assert response.status_code == 200

    def test_download_link_appears_for_ready_report(
        self, mock_site_context: object, client: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_READY
        )
        report.file.save("cohort-report.pdf", ContentFile(b"%PDF-1.4 test"), save=True)
        client.force_login(_superuser())

        response = client.get(_changelist_url())

        assert _download_url(report.pk) in response.content.decode()

    def test_download_link_absent_for_pending_report(
        self, mock_site_context: object, client: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )
        client.force_login(_superuser())

        response = client.get(_changelist_url())

        assert _download_url(report.pk) not in response.content.decode()

    def test_changelist_html_contains_no_raw_storage_url(
        self, mock_site_context: object, client: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_READY
        )
        report.file.save("cohort-report.pdf", ContentFile(b"%PDF-1.4 test"), save=True)
        client.force_login(_superuser())

        response = client.get(_changelist_url())

        assert report.file.url not in response.content.decode()


class TestGeneratedReportAdminPermissions:
    def test_add_view_is_blocked(
        self, mock_site_context: object, client: object
    ) -> None:
        client.force_login(_superuser())

        response = client.get(_add_url())

        assert response.status_code == 403

    def test_change_view_get_renders_read_only(
        self, mock_site_context: object, client: object
    ) -> None:
        """has_view_permission is untouched, so GET renders read-only -- the
        block is on saving a change, exercised below."""
        cohort = CohortFactory()
        report = GeneratedReportFactory(cohort=cohort)
        client.force_login(_superuser())

        response = client.get(_change_url(report.pk))

        assert response.status_code == 200

    def test_change_view_post_is_blocked(
        self, mock_site_context: object, client: object
    ) -> None:
        cohort = CohortFactory()
        report = GeneratedReportFactory(
            cohort=cohort, status=GeneratedReport.STATUS_PENDING
        )
        client.force_login(_superuser())

        response = client.post(
            _change_url(report.pk), data={"status": GeneratedReport.STATUS_READY}
        )

        assert response.status_code == 403
        report.refresh_from_db()
        assert report.status == GeneratedReport.STATUS_PENDING
