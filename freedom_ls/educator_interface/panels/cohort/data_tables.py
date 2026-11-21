"""The cohort tables: the organisation's cohorts and a learner's cohorts."""

from __future__ import annotations

from typing import cast

from django.db.models import Count, Prefetch, Q, QuerySet
from django.http import HttpRequest

from freedom_ls.educator_interface.panels.common.filters import VisibleCourseFilter
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.educator_interface.panels.common.tables import (
    _active_status_column,
    _interface_link,
)
from freedom_ls.learner_management.models import Cohort, CohortCourseRegistration
from freedom_ls.learner_management.queries import cohorts_visible_to
from freedom_ls.panel_framework.filters import TableFilter, ToggleFilter
from freedom_ls.panel_framework.tables import Column, DataTable, TableQuery

__all__ = [
    "CohortDataTable",
    "LearnerCohortDataTable",
]


class CohortDataTable(DataTable):
    empty_message = "No cohorts yet. Cohorts you create will appear here."
    empty_no_results = "No cohorts match these filters."
    search_fields = ["name"]
    default_sort = "name"
    #: The key of the toggle that widens the table to inactive cohorts.
    inactive_toggle_key = "inactive"

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        request = cast(OrganisationScopedRequest, request)
        return (
            cohorts_visible_to(request.user, request.organisation)
            .annotate(
                learner_count=Count(
                    "cohortmembership",
                    filter=Q(cohortmembership__learner__is_active=True),
                    distinct=True,
                ),
            )
            .prefetch_related(
                Prefetch(
                    "course_registrations",
                    queryset=CohortCourseRegistration.objects.filter(is_active=True)
                    .select_related("course")
                    .prefetch_related("course__organisations"),
                )
            )
            .order_by("name", "pk")
        )

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            _interface_link(
                "Name",
                "name",
                "cohorts/{pk}",
                sortable=True,
                card="primary",
                quick_view=True,
            ),
            _active_status_column("Status", "is_active"),
            Column(
                header="Learners",
                template_name="cotton/data-table-cells/text.html",
                attr="learner_count",
                sortable=True,
            ),
            Column(
                header="Courses",
                template_name="educator_interface/data-table-cells/cohort_courses.html",
            ),
            Column(
                header="Created",
                template_name="cotton/data-table-cells/datetime.html",
                attr="created_at",
                sortable=True,
                card="md_only",
            ),
        ]

    @staticmethod
    def get_row_label(row: object) -> str:
        return cast(Cohort, row).name

    @classmethod
    def get_filters(cls) -> list[TableFilter]:
        return [
            ToggleFilter(cls.inactive_toggle_key, "Show inactive"),
            VisibleCourseFilter(
                "course", "Course", lookup="course_registrations__course"
            ),
        ]

    @classmethod
    def filter_queryset(
        cls,
        request: HttpRequest,
        queryset: QuerySet,
        query: TableQuery,
    ) -> QuerySet:
        # The toggle can only widen, so the table excludes inactive cohorts
        # itself whenever it offers the toggle and the toggle is unset. Another
        # toggle on the table is not this one, so the match is by key.
        offers_toggle = any(
            isinstance(f, ToggleFilter) and f.key == cls.inactive_toggle_key
            for f in cls.get_filters()
        )
        if offers_toggle and cls.inactive_toggle_key not in query.filters:
            queryset = queryset.filter(is_active=True)
        return super().filter_queryset(request, queryset, query)


class LearnerCohortDataTable(CohortDataTable):
    """The learner page's cohorts: every cohort the learner belongs to, active
    or not, with search, sort and pagination but no filters. `joined_at` is
    annotated by the panel that lists them."""

    # Joined and the Remove/Move buttons need more room than a tablet or the
    # space beside the quick view gives.
    cards_when_narrow = True
    empty_message = (
        "This learner is not in any cohorts yet. Their cohorts will appear here."
    )
    empty_no_results = "No cohorts match this search."

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            *CohortDataTable.get_columns(),
            Column(
                header="Joined",
                template_name="cotton/data-table-cells/datetime.html",
                attr="joined_at",
                sortable=True,
                card="md_only",
            ),
            Column(
                header="",
                template_name="educator_interface/data-table-cells/membership_actions.html",
                card="secondary",
            ),
        ]

    @classmethod
    def get_filters(cls) -> list[TableFilter]:
        return []
