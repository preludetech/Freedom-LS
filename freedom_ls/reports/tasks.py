"""Background task that renders one cohort's progress report to PDF.

Mirrors `webhooks/events.py`'s `@task()` wrapper delegating to a plain,
id-taking function -- the task queue only ever serialises primitive,
JSON-safe arguments, never model instances.
"""

from __future__ import annotations

from django.core.files.base import ContentFile
from django.tasks import task
from django.utils import timezone

from freedom_ls.learner_management.models import Cohort
from freedom_ls.reports.gather import ReportTooLargeError, gather_cohort_report_data
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.reports.render import ReportRenderError, render_report_pdf


@task()
def _generate_cohort_report_task(report_id: str, site_id: int) -> None:
    generate_cohort_report(report_id, site_id)


def generate_cohort_report(report_id: str, site_id: int) -> None:
    """Render `report_id`'s PDF and record the outcome on the row.

    Runs from a background task, which has no HTTP request, so every query
    here filters explicitly on `site_id` rather than relying on
    `SiteAwareManager`'s thread-local site.
    """
    report = (
        GeneratedReport.objects.filter(pk=report_id, site_id=site_id)
        .select_related("requested_by")
        .first()
    )
    if report is None:
        return

    report.status = GeneratedReport.STATUS_RUNNING
    report.started_at = timezone.now()
    report.save(update_fields=["status", "started_at"])

    try:
        # requested_by is SET_NULL, so a report outlives the account that asked
        # for it; the title page falls back to "the system" for that case.
        requested_by_name = (
            report.requested_by.display_name if report.requested_by else ""
        )
        data = gather_cohort_report_data(
            str(report.cohort_id), site_id, requested_by_name=requested_by_name
        )
        pdf_bytes = render_report_pdf(data)
        report.file.save("cohort-report.pdf", ContentFile(pdf_bytes), save=False)
        report.status = GeneratedReport.STATUS_READY
        report.error_message = ""
    except (ReportRenderError, ReportTooLargeError, Cohort.DoesNotExist) as exc:
        report.status = GeneratedReport.STATUS_FAILED
        report.error_message = str(exc)
    finally:
        # Deliberately narrow `except` above (CLAUDE.md forbids a blanket
        # `except Exception`), so a bug in the gather layer or a storage
        # backend error from file.save() propagates past it. This check is
        # what stops that from stamping finished_at while leaving status at
        # RUNNING forever -- which would permanently block this cohort from
        # generating another report, since the partial unique index only
        # allows one pending/running row per cohort. The exception itself
        # still re-raises after finally, so the worker's own error reporting
        # is unaffected.
        if report.status == GeneratedReport.STATUS_RUNNING:
            report.status = GeneratedReport.STATUS_FAILED
            report.error_message = (
                report.error_message or "Unexpected error during report generation."
            )
        report.finished_at = timezone.now()
        # "file" is included even though most failure paths never touch it --
        # file.save(..., save=False) above only writes the FieldFile's new
        # name onto the in-memory instance, it does not persist it. Without
        # "file" here, a successful render's PDF would never reach the row.
        report.save(update_fields=["status", "error_message", "finished_at", "file"])
