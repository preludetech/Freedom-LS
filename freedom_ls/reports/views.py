"""Admin-only views for the reports app.

No `urls.py`: these are wired into the admin namespace by
`GeneratedReportAdmin.get_urls()` and reachable only through
`self.admin_site.admin_view(...)`, which never exposes a public URL surface.
"""

from __future__ import annotations

from unfold.admin import ModelAdmin

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.tasks import default_task_backend
from django.urls import reverse
from django.utils.text import slugify

from freedom_ls.reports.forms import GenerateReportForm
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.reports.tasks import _generate_cohort_report_task
from freedom_ls.site_aware_models.admin import admin_page_context
from freedom_ls.student_management.models import Cohort
from freedom_ls.student_management.queries import (
    all_cohorts_visible_to,
    can_view_cohort,
)


def _has_inflight_report(cohort: Cohort) -> bool:
    """Friendly pre-check only, for the common case.

    A check-then-act pre-check loses a genuine race; the partial unique
    index in generate_report_view's `except IntegrityError` clause is the
    guard that actually holds under concurrent requests.
    """
    return GeneratedReport.objects.filter(
        cohort=cohort,
        status__in=[GeneratedReport.STATUS_PENDING, GeneratedReport.STATUS_RUNNING],
    ).exists()


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
    if not can_view_cohort(request.user, cohort):
        raise PermissionDenied

    changelist_url = reverse("admin:freedom_ls_reports_generatedreport_changelist")

    if _has_inflight_report(cohort):
        messages.info(request, "A report for this cohort is already being generated.")
        return redirect(changelist_url)

    try:
        with transaction.atomic():
            report = GeneratedReport.objects.create(
                cohort=cohort,
                # Explicit, not thread-local-derived: this must equal the
                # value the enqueued task filters every one of its queries on
                # (freedom_ls/reports/tasks.py), independent of ambient site
                # context -- a deliberate, documented exception to the usual
                # "site_id is never set by hand" rule.
                site_id=cohort.site_id,
                requested_by=request.user,
            )
            transaction.on_commit(
                lambda: default_task_backend.enqueue(
                    _generate_cohort_report_task,
                    args=[str(report.pk), cohort.site_id],
                    kwargs={},
                )
            )
    except IntegrityError:
        messages.info(request, "A report for this cohort is already being generated.")
    else:
        messages.success(request, f"Generating a progress report for {cohort.name}.")
    return redirect(changelist_url)


def download_report_view(request: HttpRequest, object_id: str) -> FileResponse:
    """Stream a ready report's PDF as a private, never-cached attachment."""
    report = get_object_or_404(
        GeneratedReport.objects.select_related("cohort"), pk=object_id
    )
    if not can_view_cohort(request.user, report.cohort):
        raise PermissionDenied
    if report.status != GeneratedReport.STATUS_READY or not report.file:
        raise Http404
    filename = f"{slugify(report.cohort.name)}-progress-report.pdf"
    try:
        file_handle = report.file.open("rb")
    except FileNotFoundError as exc:
        raise Http404 from exc
    response = FileResponse(file_handle, as_attachment=True, filename=filename)
    response["Cache-Control"] = "private, no-store, must-revalidate"
    return response
