"""The learners tables and the courses each learner reaches."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

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
)

__all__ = [
    "CohortLearnerDataTable",
    "LearnerCourseSummary",
    "LearnerDataTable",
    "_last_active_cell",
    "learner_course_summaries",
]


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
    courses: dict[UUID, Course] = {
        registration.course_id: registration.course
        for registration in learner.learnercourseregistration_set.all()
    }
    for membership in learner.cohortmembership_set.all():
        if not membership.cohort.is_active:
            continue
        for registration in membership.cohort.course_registrations.all():
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


class LearnerDataTable(DataTable):
    cards_when_narrow = True
    empty_message = "No learners yet. Learners you add or import will appear here."
    empty_no_results = "No learners match these filters."
    search_fields = ["user__first_name", "user__last_name", "user__email"]
    default_sort = "user__first_name"

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
            .annotate(last_active=Max("course_progress_records__last_accessed_time"))
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
                attr="last_active",
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
        # Every value reads the caches get_queryset prefetches or annotates,
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
    """The annotated last_active as a date, matching the on-screen cell."""
    last_active = getattr(row, "last_active", None)
    if not isinstance(last_active, datetime):
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
