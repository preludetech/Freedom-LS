"""The cohort report file download: educator_interface/panels/cohort/report_download.py."""

from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.educator_interface.tests.helpers import (
    _org_admin,
    _pdf_url,
    _ready_report,
)
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.reports.factories import GeneratedReportFactory
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.reports.tests.test_views import (
    _role_config_granting_view_cohort_only,
)
from freedom_ls.role_based_permissions.utils import assign_object_role


@pytest.fixture(autouse=True)
def _site_context(mock_site_context):
    """Every test here builds site-aware objects and assigns roles."""


@pytest.mark.django_db
class TestCohortReportDownload:
    def test_a_ready_report_downloads_as_a_private_attachment_named_for_the_cohort(
        self, logged_in_client
    ):
        organisation = OrganisationFactory(name="Acme School")
        cohort = CohortFactory(organisation=organisation, name="Year 9")
        report = _ready_report(cohort)

        response = logged_in_client(_org_admin(organisation)).get(
            _pdf_url(organisation.slug, cohort.pk, report.pk)
        )

        assert response.status_code == 200
        assert response["Cache-Control"] == "private, no-store, must-revalidate"
        assert (
            "acme-school-year-9-progress-report.pdf" in response["Content-Disposition"]
        )
        assert b"".join(response.streaming_content) == b"%PDF-1.4 bytes"

    def test_an_organisation_the_user_cannot_access_answers_404(self, logged_in_client):
        cohort = CohortFactory()
        report = _ready_report(cohort)
        outsider = _org_admin(OrganisationFactory())

        response = logged_in_client(outsider).get(
            _pdf_url(cohort.organisation.slug, cohort.pk, report.pk)
        )

        assert response.status_code == 404

    def test_a_cohort_outside_the_named_organisation_answers_404(
        self, logged_in_client
    ):
        organisation = OrganisationFactory()
        foreign = CohortFactory()
        report = _ready_report(foreign)

        response = logged_in_client(_org_admin(organisation)).get(
            _pdf_url(organisation.slug, foreign.pk, report.pk)
        )

        assert response.status_code == 404

    def test_another_cohorts_report_answers_404(self, logged_in_client):
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)
        other = CohortFactory(organisation=organisation)
        report = _ready_report(other)

        response = logged_in_client(_org_admin(organisation)).get(
            _pdf_url(organisation.slug, cohort.pk, report.pk)
        )

        assert response.status_code == 404

    @pytest.mark.parametrize(
        "status", [GeneratedReport.STATUS_PENDING, GeneratedReport.STATUS_FAILED]
    )
    def test_a_report_that_is_not_ready_answers_404(self, logged_in_client, status):
        cohort = CohortFactory()
        report = GeneratedReportFactory(cohort=cohort, status=status)

        response = logged_in_client(_org_admin(cohort.organisation)).get(
            _pdf_url(cohort.organisation.slug, cohort.pk, report.pk)
        )

        assert response.status_code == 404

    def test_a_viewer_without_the_download_capability_answers_404(
        self, logged_in_client, mock_site_context
    ):
        cohort = CohortFactory()
        report = _ready_report(cohort)
        viewer = UserFactory(staff=True)
        with _role_config_granting_view_cohort_only(mock_site_context.name):
            assign_object_role(viewer, cohort, "cohort_viewer")

            response = logged_in_client(viewer).get(
                _pdf_url(cohort.organisation.slug, cohort.pk, report.pk)
            )

        assert response.status_code == 404
