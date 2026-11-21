"""Reporting surfaces of the educator interface: files built from a cohort's people."""

from __future__ import annotations

import dataclasses
import itertools
from collections import defaultdict
from typing import Literal, cast
from uuid import UUID

from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.educator_interface.avatars import learner_avatars
from freedom_ls.educator_interface.events import (
    COHORT_CHANGED,
    LEARNER_CHANGED,
    REGISTRATION_CHANGED,
)
from freedom_ls.educator_interface.panels.common.report import (
    report_over_limit_message,
)
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.educator_interface.panels.learner.actions import (
    RegisterLearnerForCourseAction,
)
from freedom_ls.educator_interface.quick_views import (
    visible_registrations_with_progress,
)
from freedom_ls.learner_management.models import (
    Cohort,
    Learner,
)
from freedom_ls.panel_framework.actions import PanelAction
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.lazy_panels import (
    LOADED_PARAM,
    LazyBodyPanel,
    render_region,
)
from freedom_ls.panel_framework.panels import Panel, PanelStack
from freedom_ls.reports.gather import gather_learner_course_details
from freedom_ls.reports.models import GeneratedReport
from freedom_ls.reports.report_data import (
    CohortReportData,
    ConfusionBlock,
    QuizColumn,
)
from freedom_ls.reports.screen_cache import (
    cached_cohort_progress,
    cached_cohort_report,
)
from freedom_ls.reports.services import (
    is_stalled,
    latest_cohort_reports,
    recent_cohort_reports,
    request_cohort_report,
)

#: How often the downloads region asks again while a report is being generated.
REPORT_POLL_SECONDS = 3
DOWNLOAD_COHORT_REPORT = "freedom_ls_learner_management.download_cohort_report"

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
        attention = cached_cohort_progress(cast(Cohort, self.instance)).attention_list
        return {
            "attention": attention,
            "avatars": learner_avatars(
                learner.learner_id for learner in attention.learners
            ),
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
            # The attention list and the summary tables can name different
            # learners, so one lookup covers both.
            "avatars": learner_avatars(
                itertools.chain(
                    (learner.learner_id for learner in data.attention_list.learners),
                    (
                        row.learner_id
                        for section in data.courses
                        for row in section.learner_rows
                    ),
                )
            ),
            "refresh_url": f"{self.ctx.base_url}?{LOADED_PARAM}=1&{REFRESH_PARAM}=1",
        }


class CohortReportStack(PanelStack):
    title = "Report"
    refresh_events = (COHORT_CHANGED,)
    children = {
        "downloads": CohortReportDownloadsPanel,
        "body": CohortReportBodyPanel,
    }


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
        details = gather_learner_course_details(learner, registrations, learner.site_id)
        # The registrations' courses arrive with their organisations prefetched.
        courses = {
            registration.course_id: registration.course
            for registration in registrations
        }
        context = super().get_context_data()
        # Each course's detail beside who shares the course, when another
        # organisation owns it.
        context["details"] = [
            (detail, courses[detail.course_id].shared_by(request.organisation))
            for detail in details
        ]
        return context
