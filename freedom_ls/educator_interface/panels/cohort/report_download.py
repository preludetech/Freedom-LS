"""The cohort report file download view."""

from __future__ import annotations

from typing import cast

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpRequest
from django.shortcuts import get_object_or_404

from freedom_ls.educator_interface.panels.cohort.config import CohortConfig
from freedom_ls.educator_interface.panels.cohort.report_panels import (
    DOWNLOAD_COHORT_REPORT,
)
from freedom_ls.educator_interface.views import _attach_organisation
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.models import Cohort
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.reports.services import report_file_response

__all__ = ["_scoped_cohort", "cohort_report_download"]


def _scoped_cohort(
    request: HttpRequest, organisation_slug: str, cohort_pk: str
) -> Cohort:
    """The cohort named in a file URL, after the organisation and cohort checks a page runs."""
    _attach_organisation(request, organisation_slug)
    return cast(Cohort, CohortConfig.get_instance_view(request, cohort_pk).instance)


@login_required
def cohort_report_download(
    request: HttpRequest, organisation_slug: str, cohort_pk: str, report_pk: str
) -> FileResponse:
    cohort = _scoped_cohort(request, organisation_slug, cohort_pk)
    report = get_object_or_404(
        GeneratedReport.objects.select_related("cohort__organisation"),
        pk=report_pk,
        cohort=cohort,
    )
    if not can(request.user, DOWNLOAD_COHORT_REPORT, cohort):
        raise Http404
    return report_file_response(report)
