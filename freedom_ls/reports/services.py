"""Starting, finding and serving cohort reports, shared by the admin and the educator interface."""

from __future__ import annotations

import dataclasses

from django.db import IntegrityError, transaction
from django.http import FileResponse, Http404
from django.tasks import default_task_backend
from django.utils.text import slugify

from freedom_ls.accounts.models import User
from freedom_ls.learner_management.models import Cohort
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.reports.tasks import _generate_cohort_report_task

IN_FLIGHT_STATUSES = (GeneratedReport.STATUS_PENDING, GeneratedReport.STATUS_RUNNING)


@dataclasses.dataclass(frozen=True)
class CohortReportState:
    in_flight: GeneratedReport | None
    ready: GeneratedReport | None
    #: A failure newer than `ready`, or None.
    failed: GeneratedReport | None


def has_inflight_report(cohort: Cohort) -> bool:
    """Friendly pre-check only, for the common case.

    A check-then-act pre-check loses a genuine race; the partial unique
    index behind request_cohort_report's IntegrityError clause is the guard
    that holds under concurrent requests.
    """
    return GeneratedReport.objects.filter(
        cohort=cohort, status__in=IN_FLIGHT_STATUSES
    ).exists()


def request_cohort_report(cohort: Cohort, user: User) -> GeneratedReport | None:
    """Start a report for the cohort, or return None when one is already being generated."""
    if has_inflight_report(cohort):
        return None
    try:
        with transaction.atomic():
            report: GeneratedReport = GeneratedReport.objects.create(
                cohort=cohort,
                # Explicit, not thread-local-derived: this must equal the
                # value the enqueued task filters every one of its queries
                # on, independent of ambient site context. A deliberate,
                # documented exception to the usual "site_id is never set
                # by hand" rule.
                site_id=cohort.site_id,
                requested_by=user,
            )
            transaction.on_commit(
                lambda: default_task_backend.enqueue(
                    _generate_cohort_report_task,
                    args=[str(report.pk), cohort.site_id],
                    kwargs={},
                )
            )
    except IntegrityError:
        return None
    return report


def report_file_response(report: GeneratedReport) -> FileResponse:
    """Stream a ready report as a private attachment; anything else is a 404."""
    if report.status != GeneratedReport.STATUS_READY or not report.file:
        raise Http404
    # allow_unicode=True: the default ASCII-only slugify drops a wholly
    # non-Latin organisation name entirely, which would silently omit the
    # organisation from the filename for exactly the tenants whose name
    # matters most.
    filename = (
        f"{slugify(report.cohort.organisation.name, allow_unicode=True)}-"
        f"{slugify(report.cohort.name, allow_unicode=True)}-progress-report.pdf"
    )
    try:
        file_handle = report.file.open("rb")
    except FileNotFoundError as exc:
        raise Http404 from exc
    response = FileResponse(file_handle, as_attachment=True, filename=filename)
    response["Cache-Control"] = "private, no-store, must-revalidate"
    return response


def latest_cohort_reports(cohort: Cohort) -> CohortReportState:
    """The in-flight report, the newest ready one, and a failure newer than that.

    One query: select_related is applied to the base queryset before the
    three filters so every member of the union selects the same columns.
    """
    reports = GeneratedReport.objects.filter(cohort=cohort).select_related(
        "requested_by"
    )
    newest_by_status: dict[str, GeneratedReport] = {}
    for report in (
        reports.filter(status__in=IN_FLIGHT_STATUSES)
        .order_by("-requested_at")[:1]
        .union(
            reports.filter(status=GeneratedReport.STATUS_READY).order_by(
                "-requested_at"
            )[:1],
            reports.filter(status=GeneratedReport.STATUS_FAILED).order_by(
                "-requested_at"
            )[:1],
        )
    ):
        newest_by_status.setdefault(report.status, report)
    in_flight = next(
        (
            newest_by_status[status]
            for status in IN_FLIGHT_STATUSES
            if status in newest_by_status
        ),
        None,
    )
    ready = newest_by_status.get(GeneratedReport.STATUS_READY)
    failed = newest_by_status.get(GeneratedReport.STATUS_FAILED)
    if (
        failed is not None
        and ready is not None
        and failed.requested_at <= ready.requested_at
    ):
        failed = None
    return CohortReportState(in_flight=in_flight, ready=ready, failed=failed)
