"""The course list table and the course registration tables."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast
from uuid import UUID

from django.core.paginator import Page
from django.db.models import Count, Prefetch, Q, QuerySet
from django.http import HttpRequest

from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.educator_interface.panels.common.tables import (
    _active_status_column,
    _cohort_links_column,
    _course_title_column,
    _interface_link,
    _learner_column,
    _registration_columns,
)
from freedom_ls.learner_management.models import (
    CohortCourseRegistration,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.queries import (
    cohorts_visible_to,
    courses_visible_to,
    learners_visible_to,
)
from freedom_ls.panel_framework.tables import Column, DataTable, TableQuery

__all__ = [
    "CourseCohortRegistrationDataTable",
    "CourseDataTable",
    "CourseLearnerRegistrationDataTable",
]


class CourseDataTable(DataTable):
    empty_message = "Courses available to your organisation will appear here."
    empty_no_results = "No courses match these filters."

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        # Counts and cells are narrowed to the cohorts and learners this
        # educator may see, so another organisation's cohorts never show
        # through a course shared with this one.
        scoped = cast(OrganisationScopedRequest, request)
        visible_cohorts = cohorts_visible_to(scoped.user, scoped.organisation)
        visible_learners = learners_visible_to(scoped.user, scoped.organisation)
        qs: QuerySet = (
            courses_visible_to(scoped.user, scoped.organisation)
            .annotate(
                cohort_count=Count(
                    "cohort_registrations",
                    filter=Q(cohort_registrations__is_active=True)
                    & Q(cohort_registrations__cohort__is_active=True)
                    & Q(cohort_registrations__cohort__in=visible_cohorts),
                    distinct=True,
                ),
                direct_learner_count=Count(
                    "learner_registrations",
                    filter=Q(learner_registrations__is_active=True)
                    & Q(learner_registrations__learner__in=visible_learners),
                    distinct=True,
                ),
                interest_count=Count("interests", distinct=True),
            )
            .prefetch_related(
                "organisations",
                Prefetch(
                    "cohort_registrations",
                    queryset=CohortCourseRegistration.objects.filter(
                        cohort__in=visible_cohorts, cohort__is_active=True
                    ).prefetch_related("cohort__cohortmembership_set__learner"),
                ),
                Prefetch(
                    "learner_registrations",
                    queryset=LearnerCourseRegistration.objects.filter(
                        learner__in=visible_learners
                    ).select_related("learner"),
                ),
            )
            .order_by("title")
        )
        return qs

    @staticmethod
    def _annotate_total_learner_count(page_obj: Page) -> None:
        """Calculate total unique active users (direct + through cohorts) for each course.

        Uses .all() instead of .filter() to leverage the prefetch cache and avoid N+1 queries.
        """
        for course in page_obj.object_list:
            cohort_user_ids: set[UUID] = set()
            for cohort_reg in course.cohort_registrations.all():
                if not cohort_reg.is_active:
                    continue
                cohort_user_ids.update(
                    m.learner.user_id
                    for m in cohort_reg.cohort.cohortmembership_set.all()
                )

            direct_user_ids = {
                reg.learner.user_id
                for reg in course.learner_registrations.all()
                if reg.is_active
            }

            course.total_learner_count = len(cohort_user_ids | direct_user_ids)

    @classmethod
    def get_rows(
        cls,
        request: HttpRequest,
        queryset: QuerySet | Sequence[object],
        query: TableQuery,
    ) -> Page:
        page_obj = super().get_rows(request, queryset, query)
        cls._annotate_total_learner_count(page_obj)
        return page_obj

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            _course_title_column("Title", "title", "courses/{pk}"),
            Column(
                header="Visibility",
                template_name="cotton/data-table-cells/text.html",
                attr="get_visibility_display",
            ),
            Column(
                header="Interest",
                template_name="cotton/data-table-cells/text.html",
                attr="interest_count",
                card="md_only",
            ),
            Column(
                header="Active Learners",
                template_name="cotton/data-table-cells/text.html",
                attr="total_learner_count",
            ),
            Column(
                header="Active Cohorts",
                template_name="cotton/data-table-cells/text.html",
                attr="cohort_count",
                card="md_only",
            ),
            _cohort_links_column("cohort_registrations.all"),
        ]


class CourseCohortRegistrationDataTable(DataTable):
    empty_message = "No cohorts are registered for this course yet. Cohort registrations will appear here."
    empty_no_results = "No cohort registrations match these filters."

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        organisation = cast(OrganisationScopedRequest, request).organisation
        return (
            CohortCourseRegistration.objects.select_related("cohort", "course")
            .filter(cohort__in=cohorts_visible_to(request.user, organisation))
            .order_by("cohort__name")
        )

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            _interface_link(
                "Cohort", "cohort.name", "cohorts/{cohort.pk}", card="primary"
            ),
            _active_status_column("Cohort status", "cohort.is_active"),
            *_registration_columns(),
            Column(
                header="",
                template_name="educator_interface/data-table-cells/course_cohort_registration_actions.html",
                card="secondary",
            ),
        ]


class CourseLearnerRegistrationDataTable(DataTable):
    empty_message = "No learners are registered for this course yet. Learner registrations will appear here."
    empty_no_results = "No learner registrations match these filters."
    default_sort = "learner__user__first_name"

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        # A course can be available to several organisations, so the registrations are scoped through the organisation's learners rather than through the course.
        organisation = cast(OrganisationScopedRequest, request).organisation
        return (
            LearnerCourseRegistration.objects.select_related("learner__user", "course")
            .filter(learner__in=learners_visible_to(request.user, organisation))
            .order_by("learner__user__first_name", "learner__user__last_name")
        )

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            _learner_column("learner"),
            *_registration_columns(),
            Column(
                header="",
                template_name="educator_interface/data-table-cells/course_learner_registration_actions.html",
                card="secondary",
            ),
        ]
