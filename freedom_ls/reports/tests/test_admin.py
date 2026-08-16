"""Tests for freedom_ls.reports.admin.GeneratedReportAdmin."""

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


def _changelist_url() -> str:
    return reverse("admin:freedom_ls_reports_generatedreport_changelist")


def _add_url() -> str:
    return reverse("admin:freedom_ls_reports_generatedreport_add")


def _change_url(report_pk: object) -> str:
    return reverse("admin:freedom_ls_reports_generatedreport_change", args=[report_pk])


def _delete_url(report_pk: object) -> str:
    return reverse("admin:freedom_ls_reports_generatedreport_delete", args=[report_pk])


def _download_url(report_pk: object) -> str:
    return reverse(
        "admin:freedom_ls_reports_generatedreport_download", args=[report_pk]
    )


def _superuser() -> object:
    return UserFactory(is_staff=True, is_superuser=True)


def _restricted_staff_user(cohort: object) -> object:
    """Staff, every GeneratedReport model permission, view_cohort on one cohort."""
    user = UserFactory(is_staff=True)
    for codename in ("view_generatedreport", "delete_generatedreport"):
        assign_perm(f"freedom_ls_reports.{codename}", user)
    assign_perm("freedom_ls_student_management.view_cohort", user, cohort)
    return user


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


class TestGeneratedReportAdminObjectLevelScoping:
    """Model permissions alone must not expose other cohorts' reports."""

    def test_changelist_lists_only_reports_for_cohorts_the_user_can_view(
        self, mock_site_context: object, client: object
    ) -> None:
        permitted = CohortFactory(name="Alpha Cohort")
        other = CohortFactory(name="Bravo Cohort")
        GeneratedReportFactory(cohort=permitted, status=GeneratedReport.STATUS_READY)
        GeneratedReportFactory(cohort=other, status=GeneratedReport.STATUS_READY)
        client.force_login(_restricted_staff_user(permitted))

        response = client.get(_changelist_url())

        content = response.content.decode()
        assert "Alpha Cohort" in content
        assert "Bravo Cohort" not in content

    def test_change_view_for_another_cohorts_report_is_denied(
        self, mock_site_context: object, client: object
    ) -> None:
        """Denied as a redirect, not a 403: get_queryset hides the row before
        the change view can look it up, so the admin treats it as absent -- and
        an absent object leaks even less than a 403 would."""
        permitted = CohortFactory(name="Alpha Cohort")
        other = CohortFactory(name="Bravo Cohort")
        report = GeneratedReportFactory(cohort=other)
        client.force_login(_restricted_staff_user(permitted))

        response = client.get(_change_url(report.pk), follow=True)

        assert response.redirect_chain == [(reverse("admin:index"), 302)]
        assert "Bravo Cohort" not in response.content.decode()

    def test_delete_view_for_another_cohorts_report_is_denied(
        self, mock_site_context: object, client: object
    ) -> None:
        permitted = CohortFactory(name="Alpha Cohort")
        other = CohortFactory(name="Bravo Cohort")
        report = GeneratedReportFactory(cohort=other)
        client.force_login(_restricted_staff_user(permitted))

        response = client.get(_delete_url(report.pk), follow=True)

        assert response.redirect_chain == [(reverse("admin:index"), 302)]
        assert "Bravo Cohort" not in response.content.decode()
        assert GeneratedReport.objects.filter(pk=report.pk).exists() is True

    def test_bulk_delete_cannot_reach_another_cohorts_report(
        self, mock_site_context: object, client: object
    ) -> None:
        permitted = CohortFactory(name="Alpha Cohort")
        other = CohortFactory(name="Bravo Cohort")
        report = GeneratedReportFactory(cohort=other)
        client.force_login(_restricted_staff_user(permitted))

        client.post(
            _changelist_url(),
            data={
                "action": "delete_selected",
                "_selected_action": [str(report.pk)],
                "post": "yes",
            },
        )

        assert GeneratedReport.objects.filter(pk=report.pk).exists() is True

    def test_change_view_for_a_permitted_cohorts_report_still_renders(
        self, mock_site_context: object, client: object
    ) -> None:
        permitted = CohortFactory(name="Alpha Cohort")
        report = GeneratedReportFactory(cohort=permitted)
        client.force_login(_restricted_staff_user(permitted))

        response = client.get(_change_url(report.pk))

        assert response.status_code == 200

    def test_superuser_sees_every_cohorts_reports(
        self, mock_site_context: object, client: object
    ) -> None:
        GeneratedReportFactory(cohort=CohortFactory(name="Alpha Cohort"))
        GeneratedReportFactory(cohort=CohortFactory(name="Bravo Cohort"))
        client.force_login(_superuser())

        response = client.get(_changelist_url())

        content = response.content.decode()
        assert "Alpha Cohort" in content
        assert "Bravo Cohort" in content

    def test_superuser_can_open_any_reports_change_and_delete_views(
        self, mock_site_context: object, client: object
    ) -> None:
        report = GeneratedReportFactory(cohort=CohortFactory(name="Bravo Cohort"))
        client.force_login(_superuser())

        assert client.get(_change_url(report.pk)).status_code == 200
        assert client.get(_delete_url(report.pk)).status_code == 200
