"""The learners tables and the courses each learner reaches."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from django.core.paginator import Page
from django.db.models import Max, Model, Prefetch, QuerySet
from django.http import HttpRequest
from django.utils import timezone

from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.panels.common.badges import learner_status_badge
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.educator_interface.panels.common.tables import (
    _cohort_links_column,
    _learner_column,
)
from freedom_ls.educator_interface.panels.learner.filters import (
    LearnerCohortFilter,
    LearnerCourseFilter,
    LearnerStatusFilter,
)
from freedom_ls.learner_management.models import (
    CohortCourseRegistration,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.queries import (
    cohorts_visible_to,
    learner_status,
    learners_visible_to,
)
from freedom_ls.panel_framework.filters import TableFilter
from freedom_ls.panel_framework.tables import (
    BadgeColumn,
    Column,
    DataTable,
    ExportColumn,
    TableQuery,
)
from freedom_ls.reports.gather import (
    active_registrations,
    gather_course_details_for_learners,
)
from freedom_ls.reports.report_data import LearnerCourseDetail

__all__ = [
    "CohortLearnerDataTable",
    "LearnerCourseCell",
    "LearnerCourseSummary",
    "LearnerDataTable",
    "RankedCourseSummary",
    "_last_active_cell",
    "learner_course_cell",
    "learner_course_summaries",
    "ranked_course_summaries",
]

#: How many of a learner's courses the learners list shows before "+N more".
COURSES_SHOWN = 3


@dataclass(frozen=True)
class LearnerCourseSummary:
    """One course a learner reaches, with the furthest of their course
    progress records for it, or None when nothing has been minted yet."""

    course: Course
    progress_percentage: int | None


def learner_course_summaries(learner: Learner) -> list[LearnerCourseSummary]:
    """The courses a learner reaches through an active individual registration
    or an active registration of an active cohort, in the order found.

    Reads only the caches `LearnerDataTable.get_queryset` prefetches, so a
    page of learners costs the same number of queries as one learner.
    """
    courses: dict[UUID, Course] = {}
    for registration in active_registrations(learner):
        courses.setdefault(registration.course_id, registration.course)

    furthest: dict[UUID, int] = {}
    for record in learner.course_progress_records.all():
        furthest[record.course_id] = max(
            furthest.get(record.course_id, 0), record.progress_percentage
        )
    return [
        LearnerCourseSummary(course, furthest.get(course_id))
        for course_id, course in courses.items()
    ]


@dataclass(frozen=True)
class RankedCourseSummary:
    """One course in a learner's Courses cell: recomputed completion, whether
    any of its registrations is flagged, and its latest activity."""

    course: Course
    progress_percentage: int
    flagged: bool
    last_activity: datetime | None


def _rank(summary: RankedCourseSummary) -> tuple[int, bool, float, str]:
    """Flagged courses need the educator first, then the ones under way; within
    a group the most recent activity comes first, no activity last, ties by title."""
    percentage = summary.progress_percentage
    group = 0 if summary.flagged else 1 if 0 < percentage < 100 else 2
    latest = summary.last_activity
    return (
        group,
        latest is None,
        -latest.timestamp() if latest else 0.0,
        summary.course.title,
    )


def ranked_course_summaries(
    learner: Learner, details: list[LearnerCourseDetail]
) -> list[RankedCourseSummary]:
    """One summary per course the learner holds, ranked for the Courses cell.

    A course held through a cohort and individually has one detail per
    registration: its percentage is the highest of them, it is flagged when any
    of them is, and its activity is the latest `last_accessed_time` across the
    learner's course progress records for it.
    """
    courses = {
        registration.course_id: registration.course
        for registration in active_registrations(learner)
    }
    last_activity: dict[UUID, datetime] = {}
    for record in learner.course_progress_records.all():
        accessed = record.last_accessed_time
        latest = last_activity.get(record.course_id)
        if accessed is not None and (latest is None or accessed > latest):
            last_activity[record.course_id] = accessed
    percentage: dict[UUID, int] = {}
    flagged: set[UUID] = set()
    for detail in details:
        percentage[detail.course_id] = max(
            percentage.get(detail.course_id, 0), detail.completion_percentage
        )
        if detail.flags:
            flagged.add(detail.course_id)
    return sorted(
        (
            RankedCourseSummary(
                course,
                percentage.get(course_id, 0),
                course_id in flagged,
                last_activity.get(course_id),
            )
            for course_id, course in courses.items()
        ),
        key=_rank,
    )


_COURSE_DETAILS_KEY = "_page_course_details"


def attach_course_details(learner: Learner, details: list[LearnerCourseDetail]) -> None:
    """Hold the page-wide gather's details for `learner` on the instance, for the
    Courses cell to read."""
    vars(learner)[_COURSE_DETAILS_KEY] = details


def attached_course_details(learner: Learner) -> list[LearnerCourseDetail] | None:
    return cast(
        "list[LearnerCourseDetail] | None", vars(learner).get(_COURSE_DETAILS_KEY)
    )


@dataclass(frozen=True)
class LearnerCourseCell:
    """The courses one learner's Courses cell shows, and how many it leaves out."""

    shown: Sequence[RankedCourseSummary] | Sequence[LearnerCourseSummary]
    hidden_count: int


def learner_course_cell(learner: Learner) -> LearnerCourseCell:
    """The capped courses for the cell: ranked when the page-wide gather ran,
    otherwise in the order found."""
    details = attached_course_details(learner)
    summaries: Sequence[RankedCourseSummary] | Sequence[LearnerCourseSummary] = (
        learner_course_summaries(learner)
        if details is None
        else ranked_course_summaries(learner, details)
    )
    return LearnerCourseCell(
        summaries[:COURSES_SHOWN], max(0, len(summaries) - COURSES_SHOWN)
    )


class LearnerDataTable(DataTable):
    cards_when_narrow = True
    empty_message = "No learners yet. Learners you add or import will appear here."
    empty_no_results = "No learners match these filters."
    search_fields = ["user__first_name", "user__last_name", "user__email"]
    default_sort = "user__first_name"

    @classmethod
    def get_rows(
        cls,
        request: HttpRequest,
        queryset: QuerySet | Sequence[object],
        query: TableQuery,
    ) -> Page:
        """The page of learners, each carrying the page's one course gather."""
        page = super().get_rows(request, queryset, query)
        learners = cast("list[Learner]", list(page.object_list))
        if learners:
            details = gather_course_details_for_learners(learners, learners[0].site_id)
            for learner in learners:
                attach_course_details(learner, details[learner.pk])
        page.object_list = learners
        return page

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        request = cast(OrganisationScopedRequest, request)
        organisation = request.organisation
        return (
            learners_visible_to(request.user, organisation, include_inactive=True)
            .select_related("user", "organisation")
            .prefetch_related(
                # A Learner belongs to exactly one organisation, so the course
                # registrations hanging off it are already organisation-local.
                # Its cohort memberships are not narrowed by that: an educator
                # holding a grant on one cohort would otherwise have the
                # organisation's other cohorts named -- and linked -- in the
                # Cohorts cell, which reads this relation through .all().
                Prefetch(
                    "cohortmembership_set",
                    queryset=CohortMembership.objects.filter(
                        cohort__in=cohorts_visible_to(request.user, organisation)
                    ).select_related("cohort"),
                ),
                Prefetch(
                    "cohortmembership_set__cohort__course_registrations",
                    queryset=CohortCourseRegistration.objects.filter(is_active=True)
                    .select_related("course")
                    .prefetch_related("course__organisations"),
                ),
                Prefetch(
                    "learnercourseregistration_set",
                    queryset=LearnerCourseRegistration.objects.filter(is_active=True)
                    .select_related("course")
                    .prefetch_related("course__organisations"),
                ),
                "course_progress_records",
            )
            .order_by("user__first_name", "user__last_name")
        )

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            _learner_column(),
            BadgeColumn(
                header="Status",
                template_name="cotton/data-table-cells/badge.html",
                badge=lambda row: learner_status_badge(cast(Learner, row)),
            ),
            _cohort_links_column("cohortmembership_set.all"),
            Column(
                header="Courses",
                template_name="educator_interface/data-table-cells/learner_courses.html",
            ),
            Column(
                header="Last active",
                template_name="cotton/data-table-cells/date.html",
                attr="user.last_active",
                sortable=True,
                empty_text="Never",
            ),
        ]

    @staticmethod
    def get_row_label(row: object) -> str:
        return cast(Learner, row).user.display_name

    @staticmethod
    def get_filters() -> list[TableFilter]:
        return [
            LearnerStatusFilter(),
            LearnerCohortFilter("cohort", "Cohort"),
            LearnerCourseFilter("course", "Course"),
        ]

    @staticmethod
    def get_export_columns() -> list[ExportColumn]:
        # Every value reads the caches get_queryset prefetches or selects,
        # so the export streams without a query per learner.
        return [
            ExportColumn("Name", "user.display_name"),
            ExportColumn("Email", "user.email"),
            ExportColumn(
                "Status", lambda row: learner_status(cast(Learner, row)).label
            ),
            ExportColumn(
                "Cohorts",
                lambda row: ", ".join(
                    membership.cohort.name
                    for membership in cast(Learner, row).cohortmembership_set.all()
                ),
            ),
            ExportColumn(
                "Courses",
                lambda row: ", ".join(
                    summary.course.label_for(cast(Learner, row).organisation)
                    for summary in learner_course_summaries(cast(Learner, row))
                ),
            ),
            ExportColumn("Last active", _last_active_cell),
        ]


def _last_active_cell(row: Model) -> str:
    """The user's last_active as a date, matching the on-screen cell."""
    last_active = cast(Learner, row).user.last_active
    if last_active is None:
        return ""
    return timezone.localtime(last_active).strftime("%Y-%m-%d")


class CohortLearnerDataTable(LearnerDataTable):
    """The cohort page's learners: the learners table plus a Remove cell."""

    empty_message = (
        "This cohort has no learners yet. Learners you add to it will appear here."
    )

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            *LearnerDataTable.get_columns(),
            Column(
                header="",
                template_name="educator_interface/data-table-cells/membership_actions.html",
                card="secondary",
            ),
        ]
