"""The panels listing a course's cohort and direct registrations."""

from __future__ import annotations

from typing import cast

from django.db.models import QuerySet
from django.http import HttpRequest

from freedom_ls.educator_interface.events import (
    COHORT_CHANGED,
    LEARNER_CHANGED,
    REGISTRATION_CHANGED,
)
from freedom_ls.educator_interface.panels.common.registration_actions import (
    CHANGE_COHORT_REGISTRATION,
    CHANGE_LEARNER_REGISTRATION,
)
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.educator_interface.panels.course.actions import (
    DeactivateCourseCohortRegistrationAction,
    DeactivateCourseLearnerRegistrationAction,
    ReactivateCourseLearnerRegistrationAction,
    RegisterCohortOnCourseAction,
    RegisterLearnerOnCourseAction,
)
from freedom_ls.educator_interface.panels.course.data_tables import (
    CourseCohortRegistrationDataTable,
    CourseLearnerRegistrationDataTable,
)
from freedom_ls.learner_management.queries import (
    cohorts_visible_to,
    learners_permitted_for,
)
from freedom_ls.panel_framework.actions import PanelAction
from freedom_ls.panel_framework.panels import DataTablePanel

__all__ = ["CourseCohortRegistrationsPanel", "CourseLearnerRegistrationsPanel"]


class CourseCohortRegistrationsPanel(DataTablePanel):
    title = "Cohort registrations"
    data_table = CourseCohortRegistrationDataTable
    table_key = "cohort_registrations"
    refresh_events = (REGISTRATION_CHANGED, COHORT_CHANGED)

    def get_actions(self) -> list[PanelAction]:
        # Deactivate renders per row, not in the footer: the actions cell
        # reads its URL from row_action_urls.
        return [
            RegisterCohortOnCourseAction(),
            DeactivateCourseCohortRegistrationAction(),
        ]

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        # The active cohorts whose registrations this educator may change,
        # computed once so each row's check is a set lookup.
        request = cast(OrganisationScopedRequest, self.request)
        context["registration_row_ids"] = set(
            cohorts_visible_to(
                request.user,
                request.organisation,
                capability=CHANGE_COHORT_REGISTRATION,
            )
            .filter(is_active=True)
            .values_list("pk", flat=True)
        )
        return context

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).filter(course=self.instance)


class CourseLearnerRegistrationsPanel(DataTablePanel):
    title = "Direct registrations"
    data_table = CourseLearnerRegistrationDataTable
    table_key = "learner_registrations"
    refresh_events = (REGISTRATION_CHANGED, LEARNER_CHANGED)

    def get_actions(self) -> list[PanelAction]:
        # Deactivate and Reactivate render per row, not in the footer: the
        # actions cell reads their URLs from row_action_urls.
        return [
            RegisterLearnerOnCourseAction(),
            DeactivateCourseLearnerRegistrationAction(),
            ReactivateCourseLearnerRegistrationAction(),
        ]

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        # The learners whose registrations this educator may change, computed
        # once so each row's check is a set lookup.
        request = cast(OrganisationScopedRequest, self.request)
        context["registration_row_ids"] = set(
            learners_permitted_for(
                request.user, request.organisation, CHANGE_LEARNER_REGISTRATION
            ).values_list("pk", flat=True)
        )
        return context

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).filter(course=self.instance)
