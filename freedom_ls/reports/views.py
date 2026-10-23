"""Admin-only views for the reports app.

No `urls.py`: these are wired into the admin namespace by
`GeneratedReportAdmin.get_urls()` and reachable only through
`self.admin_site.admin_view(...)`, which never exposes a public URL surface.
"""

from __future__ import annotations

from typing import cast

from unfold.admin import ModelAdmin

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from freedom_ls.accounts.models import User
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.queries import all_cohorts_visible_to
from freedom_ls.reports.forms import GenerateReportForm
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.reports.services import report_file_response, request_cohort_report
from freedom_ls.site_aware_models.admin import admin_page_context


def generate_report_view(
    request: HttpRequest, *, model_admin: ModelAdmin
) -> HttpResponse:
    """GET renders the cohort dropdown; POST starts a report for one.

    `self.admin_site.admin_view()` (see `GeneratedReportAdmin.get_urls()`)
    only guarantees staff status -- the object-level permission check below
    is separate and mandatory.
    """
    cohorts = (
        all_cohorts_visible_to(request.user)
        .select_related("organisation")
        .order_by("organisation__name", "name")
    )

    if request.method != "POST":
        context = {
            "form": GenerateReportForm(cohorts=cohorts),
            **admin_page_context(request, model_admin, "Generate cohort report"),
        }
        return render(request, "admin/reports/generate_form.html", context)

    form = GenerateReportForm(request.POST, cohorts=cohorts)
    if not form.is_valid():
        # The dropdown only ever offers cohorts the user may view, so an
        # invalid choice means a tampered POST -- the same 404 the queryset
        # lookup used to raise.
        raise Http404
    cohort = form.cleaned_data["cohort"]
    if not can(
        request.user, "freedom_ls_learner_management.download_cohort_report", cohort
    ):
        raise PermissionDenied

    changelist_url = reverse("admin:freedom_ls_reports_generatedreport_changelist")

    if request_cohort_report(cohort, cast(User, request.user)) is None:
        messages.info(request, "A report for this cohort is already being generated.")
    else:
        messages.success(request, f"Generating a progress report for {cohort.name}.")
    return redirect(changelist_url)


def download_report_view(request: HttpRequest, object_id: str) -> FileResponse:
    """Stream a ready report's PDF as a private, never-cached attachment."""
    report = get_object_or_404(
        GeneratedReport.objects.select_related("cohort__organisation"), pk=object_id
    )
    if not can(
        request.user,
        "freedom_ls_learner_management.download_cohort_report",
        report.cohort,
    ):
        raise PermissionDenied
    return report_file_response(report)
