"""Reporting surfaces of the educator interface: files built from a cohort's people."""

from __future__ import annotations

import dataclasses
import statistics
from collections import defaultdict
from datetime import datetime
from functools import cached_property
from typing import TYPE_CHECKING, Literal, cast
from uuid import UUID

from django.db.models import Count, Prefetch, QuerySet
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.educator_interface.actions import RegisterLearnerForCourseAction
from freedom_ls.educator_interface.events import (
    COHORT_CHANGED,
    LEARNER_CHANGED,
    REGISTRATION_CHANGED,
)
from freedom_ls.educator_interface.quick_views import (
    visible_registrations_with_progress,
)
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
)
from freedom_ls.learner_management.queries import (
    cohort_learner_count,
    cohorts_visible_to,
)
from freedom_ls.panel_framework.actions import PanelAction
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.lazy_panels import (
    LOADED_PARAM,
    LazyBodyPanel,
    render_region,
)
from freedom_ls.panel_framework.panels import Panel, PanelStack
from freedom_ls.panel_framework.views import StatusBadge
from freedom_ls.reports.config import config as reports_config
from freedom_ls.reports.gather import gather_learner_course_details
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.reports.report_data import (
    ATTENTION_LIST_MAX,
    AtRiskFlag,
    CohortProgressData,
    CohortReportData,
    ConfusionBlock,
    QuizColumn,
    over_limit_message,
)
from freedom_ls.reports.screen_cache import (
    cached_cohort_progress,
    cached_cohort_progress_many,
    cached_cohort_report,
)
from freedom_ls.reports.services import (
    is_stalled,
    latest_cohort_reports,
    recent_cohort_reports,
    request_cohort_report,
)
from freedom_ls.reports.statuses import ProgressStatus, progress_status

if TYPE_CHECKING:
    from freedom_ls.educator_interface.views import OrganisationScopedRequest

#: How often the downloads region asks again while a report is being generated.
REPORT_POLL_SECONDS = 3
DOWNLOAD_COHORT_REPORT = "freedom_ls_learner_management.download_cohort_report"

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


def report_over_limit_message(cohort: Cohort) -> str:
    """Why no report can be generated for `cohort`, or "" while it is within the limit.

    The limit is a resource guard the task enforces when it builds the
    roster; checking the active learner count up front keeps the Downloads
    card from offering a report that can only fail.
    """
    learner_count = cohort_learner_count(cohort)
    limit = reports_config.REPORTS_MAX_LEARNERS
    if learner_count <= limit:
        return ""
    return over_limit_message(cohort.name, learner_count, limit)


#: How many finished reports the Downloads table lists.
DOWNLOADS_LISTED = 5


@dataclasses.dataclass(frozen=True)
class DownloadRow:
    """One row of the Downloads table: a report and how it is shown."""

    report: GeneratedReport
    kind: Literal["ready", "in_flight", "stalled", "failed"]
    pdf_url: str = ""


class GenerateReportAction(PanelAction):
    label = "Generate report"
    action_name = "generate_report"
    capability = DOWNLOAD_COHORT_REPORT
    # The downloads panel draws its own button, in the card header, from
    # row_action_urls.
    renders_in_footer = False

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        cohort = cast(Cohort, ctx.instance)
        if report_over_limit_message(cohort):
            # The region explains why; no job is written for a report that
            # cannot be built.
            return render_region(CohortReportDownloadsPanel(ctx), status=422)
        request_cohort_report(cohort, cast(User, ctx.request.user))
        # A lost race returns None, and the region reads the in-flight row
        # either way, so the losing request sees the same state the winner does.
        return render_region(CohortReportDownloadsPanel(ctx))


class CohortReportDownloadsPanel(Panel):
    """Generate the cohort's PDF report and download the recent ones.

    The Generate button sits in the card header, outside the polled region,
    and is disabled with its reason while the cohort is over the learner
    limit. The region lists the in-flight report, a failure newer than the
    newest ready report, and the last few ready reports as a table. Only for
    a role holding the download capability: without it the panel has
    nothing to offer, so the framework leaves it off the tab.
    """

    model = Cohort
    title = "Downloads"
    capability = DOWNLOAD_COHORT_REPORT
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
        stalled = is_stalled(state.in_flight, timezone.now())
        rows: list[DownloadRow] = []
        if state.in_flight is not None:
            rows.append(
                DownloadRow(state.in_flight, "stalled" if stalled else "in_flight")
            )
        if state.failed is not None:
            rows.append(DownloadRow(state.failed, "failed"))
        rows.extend(
            DownloadRow(report, "ready", _pdf_url(url_kwargs, report))
            for report in recent_cohort_reports(cohort, DOWNLOADS_LISTED)
        )
        context = super().get_context_data()
        context.update(
            cohort=cohort,
            page_url=self.ctx.page_url,
            in_flight=state.in_flight,
            is_stalled=stalled,
            rows=rows,
            over_limit_message=report_over_limit_message(cohort),
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


class CohortNeedsAttentionPanel(LazyBodyPanel):
    load_label = "Load the figures"
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
    # The quiz title, with its course added when another course in the report
    # has a quiz of the same title.
    heading: str


def _quiz_confusions(data: CohortReportData) -> list[QuizConfusionCard]:
    """The quizzes with at least one incorrect answer, in course and quiz order."""
    courses_by_title: defaultdict[str, set[UUID]] = defaultdict(set)
    for section in data.courses:
        for quiz in section.quizzes:
            courses_by_title[quiz.title].add(section.course_id)
    return [
        QuizConfusionCard(
            quiz=quiz,
            block=section.confusions_by_quiz[quiz.form_id],
            heading=(
                f"{quiz.title} ({section.title})"
                if len(courses_by_title[quiz.title]) > 1
                else quiz.title
            ),
        )
        for section in data.courses
        for quiz in section.quizzes
        if quiz.form_id in section.confusions_by_quiz
        and section.confusions_by_quiz[quiz.form_id].total
    ]


class CohortReportBodyPanel(LazyBodyPanel):
    load_label = "Load the figures"
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

    @property
    def message(self) -> str:
        return over_limit_message(
            self.cohort.name, self.learner_count, reports_config.REPORTS_MAX_LEARNERS
        )


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
    """The active cohorts the user may see, which scope every dashboard figure.

    Each cohort's active course registrations come along, so an attention row
    can name the courses a flagged cohort is registered for without a query
    per row.
    """
    return (
        cohorts_visible_to(request.user, request.organisation)
        .filter(is_active=True)
        .prefetch_related(
            Prefetch(
                "course_registrations",
                queryset=CohortCourseRegistration.objects.filter(
                    is_active=True
                ).select_related("course"),
            )
        )
        .order_by("name")
    )


def inline_figures(cohorts: list[Cohort]) -> InlineFigures:
    learners = CohortMembership.objects.filter(
        cohort__in=cohorts, learner__is_active=True
    ).aggregate(n=Count("learner_id", distinct=True))["n"]
    return InlineFigures(learner_count=learners, cohort_count=len(cohorts))


def _gather_visible(
    cohorts: list[Cohort],
) -> tuple[list[CohortGather], list[ExcludedCohort]]:
    gathers = cached_cohort_progress_many(cohorts)
    return (
        [
            (cohort, gathers.gathered[cohort.pk])
            for cohort in cohorts
            if cohort.pk in gathers.gathered
        ],
        [
            ExcludedCohort(cohort, cohort_learner_count(cohort))
            for cohort in cohorts
            if cohort.pk in gathers.refused
        ],
    )


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
    load_label = "Load the figures"
    template_name = "educator_interface/panels/dashboard.html"
    region_template_name = "educator_interface/panels/dashboard_region.html"
    skeleton_shape = "row"

    @cached_property
    def visible_cohorts(self) -> list[Cohort]:
        # Evaluated once per request: the empty check, the inline tiles and the
        # gathered figures all read the same list.
        return list(
            visible_active_cohorts(cast("OrganisationScopedRequest", self.request))
        )

    def get_context_data(self) -> dict[str, object]:
        request = cast("OrganisationScopedRequest", self.request)
        cohorts = self.visible_cohorts
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
        )
        return context

    def get_loaded_context(self) -> dict[str, object]:
        return {"figures": gathered_figures(self.visible_cohorts)}


class LearnerCoursesPanel(Panel):
    """One card per visible registration: recomputed completion, flags, completed items and quiz attempts.

    Runs live and uncached, so a refresh after an educator action reads the
    current progress.
    """

    model = Learner
    title = "Courses"
    template_name = "educator_interface/panels/learner_courses.html"
    refresh_events = (LEARNER_CHANGED, REGISTRATION_CHANGED)

    def get_actions(self) -> list[PanelAction]:
        # Register for a course sits with the registrations it adds to.
        return [RegisterLearnerForCourseAction()]

    def get_context_data(self) -> dict[str, object]:
        learner = cast(Learner, self.instance)
        request = cast("OrganisationScopedRequest", self.request)
        registrations = [
            entry.registration
            for entry in sorted(
                visible_registrations_with_progress(learner, request),
                key=lambda entry: entry.course.title,
            )
        ]
        context = super().get_context_data()
        context["details"] = gather_learner_course_details(
            learner, registrations, learner.site_id
        )
        return context
