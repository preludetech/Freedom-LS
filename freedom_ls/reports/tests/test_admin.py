"""Tests for freedom_ls.reports.admin.GeneratedReportAdmin."""

from __future__ import annotations

import pytest
from guardian.shortcuts import assign_perm

from django.core.files.base import ContentFile
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.reports.factories import GeneratedReportFactory
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.role_based_permissions.utils import assign_object_role

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
    """Staff, model-level view and delete on GeneratedReport, view_cohort on one cohort."""
    user = UserFactory(is_staff=True)
    for codename in ("view_generatedreport", "delete_generatedreport"):
        assign_perm(f"freedom_ls_reports.{codename}", user)
    assign_perm("freedom_ls_learner_management.view_cohort", user, cohort)
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

    def test_superuser_can_open_any_reports_change_view(
        self, mock_site_context: object, client: object
    ) -> None:
        report = GeneratedReportFactory(cohort=CohortFactory(name="Bravo Cohort"))
        client.force_login(_superuser())

        response = client.get(_change_url(report.pk))

        assert response.status_code == 200

    def test_superuser_can_open_any_reports_delete_view(
        self, mock_site_context: object, client: object
    ) -> None:
        report = GeneratedReportFactory(cohort=CohortFactory(name="Bravo Cohort"))
        client.force_login(_superuser())

        response = client.get(_delete_url(report.pk))

        assert response.status_code == 200


def _organisation_staff_user(organisation: object) -> object:
    """Staff, model-level report permissions, an organisation role and no
    per-cohort guardian grant at all."""
    user = UserFactory(is_staff=True)
    for codename in ("view_generatedreport", "delete_generatedreport"):
        assign_perm(f"freedom_ls_reports.{codename}", user)
    assign_object_role(user, organisation, "organisation_staff")
    return user


class TestGeneratedReportAdminOrganisationScoping:
    """An organisation role grants every cohort inside the organisation.
    Guardian cannot express that implication, so the admin must go through
    learner_management.queries rather than a bare view_cohort lookup."""

    def test_changelist_lists_reports_for_every_cohort_in_the_organisation(
        self, mock_site_context: object, client: object
    ) -> None:
        organisation = OrganisationFactory()
        GeneratedReportFactory(
            cohort=CohortFactory(name="Alpha Cohort", organisation=organisation)
        )
        GeneratedReportFactory(
            cohort=CohortFactory(name="Bravo Cohort", organisation=organisation)
        )
        client.force_login(_organisation_staff_user(organisation))

        response = client.get(_changelist_url())

        content = response.content.decode()
        assert "Alpha Cohort" in content
        assert "Bravo Cohort" in content

    def test_changelist_hides_reports_from_another_organisation(
        self, mock_site_context: object, client: object
    ) -> None:
        organisation = OrganisationFactory()
        GeneratedReportFactory(
            cohort=CohortFactory(name="Alpha Cohort", organisation=organisation)
        )
        GeneratedReportFactory(
            cohort=CohortFactory(
                name="Foreign Cohort", organisation=OrganisationFactory()
            )
        )
        client.force_login(_organisation_staff_user(organisation))

        content = client.get(_changelist_url()).content.decode()

        assert "Alpha Cohort" in content
        assert "Foreign Cohort" not in content

    def test_change_view_renders_for_a_cohort_in_the_organisation(
        self, mock_site_context: object, client: object
    ) -> None:
        organisation = OrganisationFactory()
        report = GeneratedReportFactory(cohort=CohortFactory(organisation=organisation))
        client.force_login(_organisation_staff_user(organisation))

        response = client.get(_change_url(report.pk))

        assert response.status_code == 200

    def test_change_view_for_another_organisations_report_is_denied(
        self, mock_site_context: object, client: object
    ) -> None:
        organisation = OrganisationFactory()
        report = GeneratedReportFactory(
            cohort=CohortFactory(
                name="Foreign Cohort", organisation=OrganisationFactory()
            )
        )
        client.force_login(_organisation_staff_user(organisation))

        response = client.get(_change_url(report.pk), follow=True)

        assert response.redirect_chain == [(reverse("admin:index"), 302)]
        assert "Foreign Cohort" not in response.content.decode()

    def test_delete_view_renders_for_a_cohort_in_the_organisation(
        self, mock_site_context: object, client: object
    ) -> None:
        organisation = OrganisationFactory()
        report = GeneratedReportFactory(cohort=CohortFactory(organisation=organisation))
        client.force_login(_organisation_staff_user(organisation))

        response = client.get(_delete_url(report.pk))

        assert response.status_code == 200

    def test_download_streams_for_a_cohort_in_the_organisation(
        self, mock_site_context: object, client: object
    ) -> None:
        organisation = OrganisationFactory()
        report = GeneratedReportFactory(
            cohort=CohortFactory(organisation=organisation),
            status=GeneratedReport.STATUS_READY,
        )
        report.file.save(
            "cohort-report.pdf", ContentFile(b"%PDF-1.4 test bytes"), save=True
        )
        client.force_login(_organisation_staff_user(organisation))

        response = client.get(_download_url(report.pk))

        assert response.status_code == 200

    def test_a_per_cohort_grant_still_works_without_any_organisation_role(
        self, mock_site_context: object, client: object
    ) -> None:
        """The lock-out risk: an educator holding only guardian grants must not
        lose access now that a second path exists."""
        permitted = CohortFactory(name="Alpha Cohort")
        GeneratedReportFactory(cohort=permitted)
        GeneratedReportFactory(cohort=CohortFactory(name="Bravo Cohort"))
        client.force_login(_restricted_staff_user(permitted))

        content = client.get(_changelist_url()).content.decode()

        assert "Alpha Cohort" in content
        assert "Bravo Cohort" not in content


class TestGeneratedReportAdminOrganisationColumn:
    """Two organisations on one site may both have a "Year 9 Maths", so the
    changelist has to say which one a row belongs to."""

    def test_changelist_names_each_reports_organisation(
        self, mock_site_context: object, client: object
    ) -> None:
        GeneratedReportFactory(
            cohort=CohortFactory(
                name="Year 9 Maths",
                organisation=OrganisationFactory(name="Northside College"),
            )
        )
        GeneratedReportFactory(
            cohort=CohortFactory(
                name="Year 9 Maths",
                organisation=OrganisationFactory(name="Southside College"),
            )
        )
        client.force_login(_superuser())

        content = client.get(_changelist_url()).content.decode()

        assert "Northside College" in content
        assert "Southside College" in content
