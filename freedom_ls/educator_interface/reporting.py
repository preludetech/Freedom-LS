"""Reporting surfaces of the educator interface: files built from a cohort's people."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, cast

from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import content_disposition_header
from django.utils.text import slugify

from freedom_ls.accounts.models import User
from freedom_ls.base.csv_safety import UTF8_BOM, escape_csv_formula
from freedom_ls.educator_interface.events import COHORT_CHANGED
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.models import Cohort
from freedom_ls.learner_management.queries import cohort_educators, learner_status
from freedom_ls.panel_framework.actions import PanelAction
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.panels import Panel, PanelStack
from freedom_ls.panel_framework.views import StatusBadge
from freedom_ls.reports.indexes import learner_sort_key, load_active_memberships
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.reports.report_data import AtRiskFlag, ReportTooLargeError
from freedom_ls.reports.screen_cache import cached_cohort_progress
from freedom_ls.reports.services import latest_cohort_reports, request_cohort_report
from freedom_ls.reports.statuses import ProgressStatus, progress_status

if TYPE_CHECKING:
    from freedom_ls.educator_interface.views import OrganisationScopedRequest

#: How often the downloads region asks again while a report is being generated.
REPORT_POLL_SECONDS = 3
#: An in-flight report older than this is assumed stuck, and the page stops polling for it.
IN_FLIGHT_STALL = timedelta(minutes=10)
DOWNLOAD_COHORT_REPORT = "freedom_ls_learner_management.download_cohort_report"
#: The query parameter that turns a lazy panel's skeleton into its body.
LOADED_PARAM = "loaded"

PROGRESS_STATUS_TONES = {
    ProgressStatus.NOT_STARTED: "muted",
    ProgressStatus.IN_PROGRESS: "info",
    ProgressStatus.COMPLETE: "success",
}


def progress_status_badge(completion_percentage: int) -> StatusBadge:
    """The badge for a learner's progress status, from a recomputed completion."""
    status = progress_status(completion_percentage)
    return StatusBadge(tone=PROGRESS_STATUS_TONES[status], label=status.label)


def flag_badge(flag: AtRiskFlag) -> StatusBadge:
    """The badge for an at-risk flag."""
    # A rule's severity is already a role token name, so it is the tone.
    return StatusBadge(tone=flag.severity, label=flag.label)


def cohort_members_csv_response(cohort: Cohort) -> HttpResponse:
    """The cohort's active learners, then its educators, as one formula-safe CSV.

    The body is built in memory rather than streamed: a streamed body is read
    after the site thread-local is cleared, and a cohort's membership list is
    small. learner_status reads only the loaded User row, so no query runs
    per row.
    """
    learners = sorted(
        (
            membership.learner
            for membership in load_active_memberships(cohort, cohort.site_id)
        ),
        key=lambda learner: learner_sort_key(learner.user),
    )
    buffer = io.StringIO()
    buffer.write(UTF8_BOM)
    writer = csv.writer(buffer)
    writer.writerow(["Name", "Email", "Role", "Status"])
    for learner in learners:
        writer.writerow(
            [
                escape_csv_formula(learner.user.display_name),
                escape_csv_formula(learner.user.email),
                "Learner",  # a label for the reader, not a permission role
                learner_status(learner).label,
            ]
        )
    for user, role_display_name in cohort_educators(cohort):
        writer.writerow(
            [
                escape_csv_formula(user.display_name),
                escape_csv_formula(user.email),
                escape_csv_formula(role_display_name),
                "",
            ]
        )
    response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
    # With a filename the header is always produced; None is only returned
    # when both as_attachment and filename are falsy.
    response["Content-Disposition"] = cast(
        str,
        content_disposition_header(
            as_attachment=True, filename=_members_csv_filename(cohort)
        ),
    )
    return response


def _members_csv_filename(cohort: Cohort) -> str:
    organisation = slugify(cohort.organisation.name, allow_unicode=True)
    name = slugify(cohort.name, allow_unicode=True)
    return f"{organisation}-{name}-members-{timezone.localdate():%Y-%m-%d}.csv"


def is_stalled(report: GeneratedReport | None, now: datetime) -> bool:
    """An in-flight report older than the stall window, which stops the page polling for it."""
    return report is not None and now - report.requested_at > IN_FLIGHT_STALL


def render_region(panel: Panel) -> HttpResponse:
    """A panel's refresh region on its own, the fragment a targeted swap replaces."""
    return render(
        panel.request,
        panel.region_template_name or panel.template_name,
        panel.get_context_data(),
    )


class GenerateReportAction(PanelAction):
    label = "Generate PDF report"
    action_name = "generate_report"
    capability = DOWNLOAD_COHORT_REPORT
    # The downloads region draws its own button from row_action_urls.
    renders_in_footer = False

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        request_cohort_report(cast(Cohort, ctx.instance), cast(User, ctx.request.user))
        # A lost race returns None, and the region reads the in-flight row
        # either way, so the losing request sees the same state the winner does.
        return render_region(CohortReportDownloadsPanel(ctx))


class CohortReportDownloadsPanel(Panel):
    model = Cohort
    title = "Downloads"
    template_name = "educator_interface/panels/cohort_report_downloads.html"
    region_template_name = (
        "educator_interface/panels/cohort_report_downloads_region.html"
    )
    refresh_events = (COHORT_CHANGED,)

    def get_actions(self) -> list[PanelAction]:
        return [GenerateReportAction()]

    def get_context_data(self) -> dict[str, object]:
        cohort = cast(Cohort, self.instance)
        request = cast("OrganisationScopedRequest", self.request)
        url_kwargs = {**request.panel_url_kwargs, "cohort_pk": str(cohort.pk)}
        state = latest_cohort_reports(cohort)
        context = super().get_context_data()
        context.update(
            cohort=cohort,
            page_url=self.ctx.page_url,
            can_download=can(request.user, DOWNLOAD_COHORT_REPORT, cohort),
            csv_url=reverse("educator_interface:cohort_members_csv", kwargs=url_kwargs),
            in_flight=state.in_flight,
            is_stalled=is_stalled(state.in_flight, timezone.now()),
            ready=state.ready,
            pdf_url=_pdf_url(url_kwargs, state.ready),
            failed=state.failed,
            poll_seconds=REPORT_POLL_SECONDS,
        )
        return context


def _pdf_url(url_kwargs: dict[str, str], ready: GeneratedReport | None) -> str:
    if ready is None:
        return ""
    return reverse(
        "educator_interface:cohort_report_download",
        kwargs={**url_kwargs, "report_pk": str(ready.pk)},
    )


class CohortReportStack(PanelStack):
    title = "Report"
    refresh_events = (COHORT_CHANGED,)
    children = {"downloads": CohortReportDownloadsPanel}


class LazyBodyPanel(Panel):
    """A panel whose body costs a gather: the first render is a skeleton that fetches the body.

    get_loaded_context runs only on the fetch that carries loaded=1. It may
    raise ReportTooLargeError; the region then shows the message instead of a body.
    """

    template_name = "educator_interface/panels/lazy_panel.html"
    skeleton_shape = "text"
    skeleton_lines = 3

    @property
    def is_loaded(self) -> bool:
        return self.request.GET.get(LOADED_PARAM) == "1"

    def get_loaded_context(self) -> dict[str, object]:
        return {}

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        context.update(
            is_loaded=self.is_loaded,
            loaded_url=f"{self.ctx.base_url}?{LOADED_PARAM}=1",
            skeleton_shape=self.skeleton_shape,
            skeleton_lines=self.skeleton_lines,
        )
        if self.is_loaded:
            try:
                context.update(self.get_loaded_context())
            except ReportTooLargeError as error:
                context["too_large_message"] = str(error)
        return context


class CohortNeedsAttentionPanel(LazyBodyPanel):
    model = Cohort
    title = "Needs attention"
    refresh_events = (COHORT_CHANGED,)
    skeleton_shape = "row"
    region_template_name = (
        "educator_interface/panels/cohort_needs_attention_region.html"
    )

    def get_loaded_context(self) -> dict[str, object]:
        return {
            "attention": cached_cohort_progress(
                cast(Cohort, self.instance)
            ).attention_list
        }
