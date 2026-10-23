"""Reporting surfaces of the educator interface: files built from a cohort's people."""

from __future__ import annotations

import csv
import dataclasses
import io
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, cast
from uuid import UUID

from django.db.models import Count, QuerySet
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
from freedom_ls.learner_management.models import Cohort, CohortMembership
from freedom_ls.learner_management.queries import (
    cohort_educators,
    cohort_learner_count,
    cohorts_visible_to,
    learner_status,
)
from freedom_ls.panel_framework.actions import PanelAction
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.panels import Panel, PanelStack
from freedom_ls.panel_framework.views import StatusBadge
from freedom_ls.reports.config import config as reports_config
from freedom_ls.reports.indexes import learner_sort_key, load_active_memberships
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.reports.report_data import (
    ATTENTION_LIST_MAX,
    AtRiskFlag,
    CohortProgressData,
    CohortReportData,
    ConfusionBlock,
    QuizColumn,
    ReportTooLargeError,
)
from freedom_ls.reports.screen_cache import (
    cached_cohort_progress,
    cached_cohort_report,
)
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


REFRESH_PARAM = "refresh"


@dataclasses.dataclass(frozen=True)
class QuizConfusionCard:
    quiz: QuizColumn
    block: ConfusionBlock


def _quiz_confusions(data: CohortReportData) -> list[QuizConfusionCard]:
    """The quizzes with at least one incorrect answer, in course and quiz order."""
    return [
        QuizConfusionCard(quiz=quiz, block=section.confusions_by_quiz[quiz.form_id])
        for section in data.courses
        for quiz in section.quizzes
        if quiz.form_id in section.confusions_by_quiz
        and section.confusions_by_quiz[quiz.form_id].total
    ]


class CohortReportBodyPanel(LazyBodyPanel):
    model = Cohort
    title = "Cohort report"
    refresh_events = (COHORT_CHANGED,)
    region_template_name = "educator_interface/panels/cohort_report_body_region.html"
    skeleton_lines = 8

    def get_loaded_context(self) -> dict[str, object]:
        refresh = self.request.GET.get(REFRESH_PARAM) == "1"
        data = cached_cohort_report(cast(Cohort, self.instance), refresh=refresh)
        return {
            "data": data,
            "confusions": _quiz_confusions(data),
            "refresh_url": f"{self.ctx.base_url}?{LOADED_PARAM}=1&{REFRESH_PARAM}=1",
        }


class CohortReportStack(PanelStack):
    title = "Report"
    refresh_events = (COHORT_CHANGED,)
    children = {
        "downloads": CohortReportDownloadsPanel,
        "body": CohortReportBodyPanel,
    }


@dataclasses.dataclass(frozen=True)
class InlineFigures:
    """The two dashboard tiles that need no gather."""

    learner_count: int
    cohort_count: int


@dataclasses.dataclass(frozen=True)
class CohortFlags:
    """One cohort's view of a flagged learner."""

    cohort: Cohort
    completion_percentage: int
    flags: list[AtRiskFlag]


@dataclasses.dataclass(frozen=True)
class FlaggedLearnerRow:
    """A learner flagged in at least one visible cohort, with each cohort's detail."""

    learner_id: UUID
    full_name: str
    sort_key: tuple[str, str]
    lowest_completion: int
    cohorts: list[CohortFlags]


@dataclasses.dataclass(frozen=True)
class CohortProgressRow:
    cohort: Cohort
    mean_completion: int | None
    learner_count: int
    flagged_count: int


@dataclasses.dataclass(frozen=True)
class ExcludedCohort:
    """A visible cohort over the report size limit, left out of the gathered figures."""

    cohort: Cohort
    learner_count: int


@dataclasses.dataclass(frozen=True)
class GatheredFigures:
    average_progress: int | None
    # Distinct flagged learners, not capped to the rows shown.
    attention_count: int
    # The first ATTENTION_LIST_MAX by lowest completion.
    attention_rows: list[FlaggedLearnerRow]
    cohort_rows: list[CohortProgressRow]
    excluded: list[ExcludedCohort]
    # The oldest gather behind the figures; None when no cohort was gathered.
    figures_as_of: datetime | None


type CohortGather = tuple[Cohort, CohortProgressData]


def visible_active_cohorts(request: OrganisationScopedRequest) -> QuerySet[Cohort]:
    """The active cohorts the user may see, which scope every dashboard figure."""
    return (
        cohorts_visible_to(request.user, request.organisation)
        .filter(is_active=True)
        .order_by("name")
    )


def inline_figures(cohorts: QuerySet[Cohort]) -> InlineFigures:
    learners = CohortMembership.objects.filter(
        cohort__in=cohorts, learner__is_active=True
    ).aggregate(n=Count("learner_id", distinct=True))["n"]
    return InlineFigures(learner_count=learners, cohort_count=cohorts.count())


def _gather_visible(
    cohorts: list[Cohort],
) -> tuple[list[CohortGather], list[ExcludedCohort]]:
    gathers: list[CohortGather] = []
    excluded: list[ExcludedCohort] = []
    for cohort in cohorts:
        try:
            gathers.append((cohort, cached_cohort_progress(cohort)))
        except ReportTooLargeError:
            excluded.append(ExcludedCohort(cohort, cohort_learner_count(cohort)))
    return gathers, excluded


def _average_progress(gathers: list[CohortGather]) -> int | None:
    """Each learner once, at the mean of their completion across the cohorts gathered."""
    completions: dict[UUID, list[int]] = defaultdict(list)
    for _cohort, data in gathers:
        for learner in data.learners:
            completions[learner.learner_id].append(learner.completion_percentage)
    if not completions:
        return None
    return round(
        statistics.fmean(statistics.fmean(values) for values in completions.values())
    )


def _flagged_learner_rows(gathers: list[CohortGather]) -> list[FlaggedLearnerRow]:
    by_learner: dict[UUID, FlaggedLearnerRow] = {}
    for cohort, data in gathers:
        for learner in data.learners:
            if not learner.flags:
                continue
            entry = CohortFlags(cohort, learner.completion_percentage, learner.flags)
            row = by_learner.get(learner.learner_id)
            by_learner[learner.learner_id] = (
                FlaggedLearnerRow(
                    learner.learner_id,
                    learner.full_name,
                    learner.sort_key,
                    learner.completion_percentage,
                    [entry],
                )
                if row is None
                else dataclasses.replace(
                    row,
                    lowest_completion=min(
                        row.lowest_completion, learner.completion_percentage
                    ),
                    cohorts=[*row.cohorts, entry],
                )
            )
    return sorted(
        by_learner.values(), key=lambda row: (row.lowest_completion, row.sort_key)
    )


def _cohort_rows(gathers: list[CohortGather]) -> list[CohortProgressRow]:
    rows = [
        CohortProgressRow(
            cohort,
            data.mean_completion,
            data.cohort_size,
            sum(1 for learner in data.learners if learner.flags),
        )
        for cohort, data in gathers
    ]
    # An empty cohort has no mean, so it sorts after every cohort that has one.
    return sorted(
        rows,
        key=lambda row: (
            row.mean_completion is None,
            row.mean_completion or 0,
            row.cohort.name,
        ),
    )


def gathered_figures(cohorts: list[Cohort]) -> GatheredFigures:
    """The dashboard figures that need each cohort's progress gather."""
    gathers, excluded = _gather_visible(cohorts)
    flagged = _flagged_learner_rows(gathers)
    return GatheredFigures(
        average_progress=_average_progress(gathers),
        attention_count=len(flagged),
        attention_rows=flagged[:ATTENTION_LIST_MAX],
        cohort_rows=_cohort_rows(gathers),
        excluded=excluded,
        figures_as_of=min(
            (data.generated_at for _cohort, data in gathers), default=None
        ),
    )


class DashboardPanel(LazyBodyPanel):
    """The organisation dashboard: the inline tiles at once, the gathered figures lazily."""

    title = "Reporting"
    template_name = "educator_interface/panels/dashboard.html"
    region_template_name = "educator_interface/panels/dashboard_region.html"
    skeleton_shape = "row"

    def _cohorts(self) -> QuerySet[Cohort]:
        return visible_active_cohorts(cast("OrganisationScopedRequest", self.request))

    def get_context_data(self) -> dict[str, object]:
        request = cast("OrganisationScopedRequest", self.request)
        cohorts = self._cohorts()
        context = super().get_context_data()
        context.update(
            cohorts=cohorts,
            inline=inline_figures(cohorts),
            # An organisation admin can create cohorts; a cohort-scoped role cannot.
            is_organisation_admin=can(
                request.user,
                "freedom_ls_learner_management.change_cohort",
                request.organisation,
            ),
            max_learners=reports_config.REPORTS_MAX_LEARNERS,
        )
        return context

    def get_loaded_context(self) -> dict[str, object]:
        return {"figures": gathered_figures(list(self._cohorts()))}
