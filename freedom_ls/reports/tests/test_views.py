"""Tests for freedom_ls.reports.views (the generate and download admin views)."""

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


def _generate_url() -> str:
    return reverse("admin:freedom_ls_reports_generatedreport_generate")


def _download_url(report_pk: object) -> str:
    return reverse(
        "admin:freedom_ls_reports_generatedreport_download", args=[report_pk]
    )


def _staff_user_with_cohort_view_permission(cohort: object) -> object:
    user = UserFactory(is_staff=True)
    assign_perm("freedom_ls_learner_management.view_cohort", user, cohort)
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

    def test_renders_inside_the_admin_shell_with_the_sidebar(
        self, mock_site_context: object, client: object
    ) -> None:
        cohort = CohortFactory()
        client.force_login(_staff_user_with_cohort_view_permission(cohort))

        response = client.get(_generate_url())

        # each_context is what supplies these; a hand-rolled context dict
        # silently drops the whole admin shell.
        assert response.context["is_nav_sidebar_enabled"] is True
        assert 'id="nav-sidebar"' in response.content.decode()

    def test_renders_exactly_one_h1(
        self, mock_site_context: object, client: object
    ) -> None:
        cohort = CohortFactory()
        client.force_login(_staff_user_with_cohort_view_permission(cohort))

        response = client.get(_generate_url())

        # The admin header already emits the page's h1; a second one in the
        # content block reads as the title printed twice.
        assert response.content.decode().count("<h1") == 1

    def test_breadcrumb_trail_links_back_to_the_changelist(
        self, mock_site_context: object, client: object
    ) -> None:
        cohort = CohortFactory()
        client.force_login(_staff_user_with_cohort_view_permission(cohort))

        response = client.get(_generate_url())

        changelist_url = reverse("admin:freedom_ls_reports_generatedreport_changelist")
        assert f'href="{changelist_url}"' in response.content.decode()


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


def _organisation_staff_user(organisation: object) -> object:
    """Staff with an organisation role and no per-cohort guardian grant."""
    user = UserFactory(is_staff=True)
    assign_object_role(user, organisation, "organisation_staff")
    return user


class TestGenerateReportViewOrganisationScoping:
    """The cohort dropdown and its POST re-check must honour the organisation
    role, which guardian's view_cohort can never carry."""

    def test_dropdown_offers_every_cohort_in_the_organisation(
        self, mock_site_context: object, client: object
    ) -> None:
        organisation = OrganisationFactory()
        CohortFactory(name="Alpha Cohort", organisation=organisation)
        CohortFactory(name="Bravo Cohort", organisation=organisation)
        client.force_login(_organisation_staff_user(organisation))

        content = client.get(_generate_url()).content.decode()

        assert "Alpha Cohort" in content
        assert "Bravo Cohort" in content

    def test_dropdown_omits_cohorts_from_another_organisation(
        self, mock_site_context: object, client: object
    ) -> None:
        organisation = OrganisationFactory()
        CohortFactory(name="Alpha Cohort", organisation=organisation)
        CohortFactory(name="Foreign Cohort", organisation=OrganisationFactory())
        client.force_login(_organisation_staff_user(organisation))

        content = client.get(_generate_url()).content.decode()

        assert "Alpha Cohort" in content
        assert "Foreign Cohort" not in content

    def test_post_creates_a_report_for_a_cohort_in_the_organisation(
        self, mock_site_context: object, client: object
    ) -> None:
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)
        client.force_login(_organisation_staff_user(organisation))

        client.post(_generate_url(), data={"cohort": str(cohort.pk)})

        report = GeneratedReport.objects.get(cohort=cohort)
        assert report.status == GeneratedReport.STATUS_PENDING

    def test_post_for_another_organisations_cohort_creates_nothing(
        self, mock_site_context: object, client: object
    ) -> None:
        cohort = CohortFactory(organisation=OrganisationFactory())
        client.force_login(_organisation_staff_user(OrganisationFactory()))

        response = client.post(_generate_url(), data={"cohort": str(cohort.pk)})

        assert response.status_code == 404
        assert GeneratedReport.objects.filter(cohort=cohort).count() == 0


class TestDownloadReportViewOrganisationScoping:
    def test_organisation_role_holder_downloads_a_report_in_their_organisation(
        self, mock_site_context: object, client: object
    ) -> None:
        organisation = OrganisationFactory()
        report = GeneratedReportFactory(
            cohort=CohortFactory(organisation=organisation),
            status=GeneratedReport.STATUS_READY,
        )
        _save_ready_file(report)
        client.force_login(_organisation_staff_user(organisation))

        response = client.get(_download_url(report.pk))

        assert response.status_code == 200

    def test_another_organisations_report_is_403(
        self, mock_site_context: object, client: object
    ) -> None:
        report = GeneratedReportFactory(
            cohort=CohortFactory(organisation=OrganisationFactory()),
            status=GeneratedReport.STATUS_READY,
        )
        _save_ready_file(report)
        client.force_login(_organisation_staff_user(OrganisationFactory()))

        response = client.get(_download_url(report.pk))

        assert response.status_code == 403


class TestGenerateReportViewCohortLabels:
    def test_dropdown_labels_name_the_organisation(
        self, mock_site_context: object, client: object
    ) -> None:
        """The picker is the one place an admin chooses between two cohorts
        that may legitimately share a name."""
        organisation = OrganisationFactory(name="Northside College")
        CohortFactory(name="Year 9 Maths", organisation=organisation)
        client.force_login(_organisation_staff_user(organisation))

        content = client.get(_generate_url()).content.decode()

        assert "Northside College — Year 9 Maths" in content
