"""The learner page's cohorts, registrations and history data table panels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from django.db.models import OuterRef, QuerySet, Subquery
from django.http import HttpRequest

from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.events import (
    COHORT_CHANGED,
    LEARNER_CHANGED,
    REGISTRATION_CHANGED,
)
from freedom_ls.educator_interface.panels.audit_log.data_table_panels import (
    HistoryPanel,
)
from freedom_ls.educator_interface.panels.cohort.data_tables import (
    LearnerCohortDataTable,
)
from freedom_ls.educator_interface.panels.common.badges import active_status_badge
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.educator_interface.panels.learner.actions import (
    AddToCohortAction,
    DeactivateRegistrationAction,
    MoveToCohortAction,
    ReactivateRegistrationAction,
    RemoveFromCohortAction,
)
from freedom_ls.learner_management.models import (
    CohortCourseRegistration,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.queries import (
    DELETE_COHORTMEMBERSHIP,
    available_to_organisation_expression,
    cohorts_visible_to,
)
from freedom_ls.panel_framework.actions import PanelAction
from freedom_ls.panel_framework.panels import DataTablePanel, Panel
from freedom_ls.panel_framework.views import StatusBadge

__all__ = [
    "LearnerCohortsPanel",
    "LearnerHistoryPanel",
    "LearnerRegistrationsPanel",
    "RegistrationRow",
]


class LearnerCohortsPanel(DataTablePanel):
    title = "Cohorts"
    data_table = LearnerCohortDataTable
    table_key = "cohorts"
    refresh_events = (LEARNER_CHANGED, COHORT_CHANGED)

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        joined_at = Subquery(
            CohortMembership.objects.filter(
                cohort=OuterRef("pk"), learner=self.instance
            ).values("created_at")[:1]
        )
        queryset: QuerySet = (
            super()
            .get_queryset(request)
            .filter(cohortmembership__learner=self.instance)
        )
        annotated: QuerySet = queryset.annotate(joined_at=joined_at)
        return annotated

    def get_actions(self) -> list[PanelAction]:
        # Add to cohort sits with the cohorts it changes; the row actions
        # render per row through row_action_urls.
        return [AddToCohortAction(), RemoveFromCohortAction(), MoveToCohortAction()]

    def get_context_data(self) -> dict[str, object]:
        request = cast(OrganisationScopedRequest, self.request)
        context = super().get_context_data()
        # A grant on only some of the learner's cohorts shows Remove on
        # those rows alone, and an inactive cohort offers nothing.
        context["membership_param"] = "cohort"
        context["membership_row_ids"] = set(
            cohorts_visible_to(
                request.user,
                request.organisation,
                capability=DELETE_COHORTMEMBERSHIP,
            )
            .filter(is_active=True)
            .values_list("pk", flat=True)
        )
        return context


@dataclass(frozen=True)
class RegistrationRow:
    """One course the learner is registered for on the Registrations card.
    `via` is "Individual" or "via <cohort name>"."""

    course: Course
    via: str
    is_active: bool
    registration: LearnerCourseRegistration | CohortCourseRegistration
    shared_by: str | None = None
    can_reactivate: bool = False

    @property
    def detail(self) -> str:
        """The muted line under the course title: how the learner is
        registered, then who shares the course when another organisation
        owns it."""
        return (
            f"{self.via} · Shared by {self.shared_by}" if self.shared_by else self.via
        )

    @property
    def badge(self) -> StatusBadge:
        return active_status_badge(self.is_active)

    @property
    def is_individual(self) -> bool:
        return isinstance(self.registration, LearnerCourseRegistration)


class LearnerRegistrationsPanel(Panel):
    model = Learner
    title = "Registrations"
    template_name = "educator_interface/panels/learner_registrations.html"
    refresh_events = (LEARNER_CHANGED, REGISTRATION_CHANGED)

    def get_actions(self) -> list[PanelAction]:
        return [
            DeactivateRegistrationAction(),
            ReactivateRegistrationAction(),
        ]

    def get_context_data(self) -> dict[str, object]:
        learner = cast(Learner, self.instance)
        request = cast(OrganisationScopedRequest, self.request)
        visible_cohorts = cohorts_visible_to(request.user, request.organisation)
        individual = list(
            LearnerCourseRegistration.objects.filter(learner=learner)
            .select_related("course")
            .prefetch_related("course__organisations")
        )
        # A registration through an inactive cohort is not shown at all; the
        # learner reaches that course only while the cohort is active.
        through_cohorts = (
            CohortCourseRegistration.objects.filter(
                cohort__in=visible_cohorts,
                cohort__is_active=True,
                cohort__cohortmembership__learner=learner,
            )
            .select_related("course", "cohort")
            .prefetch_related("course__organisations")
        )
        # Reactivating registers the learner again, which an educator may do
        # only for a course available to the learner's organisation.
        available_course_ids = set(
            Course.objects.filter(
                pk__in=[r.course_id for r in individual if not r.is_active]
            )
            .filter(available_to_organisation_expression(learner.organisation))
            .values_list("pk", flat=True)
        )

        def row(
            registration: LearnerCourseRegistration | CohortCourseRegistration,
            via: str,
        ) -> RegistrationRow:
            return RegistrationRow(
                registration.course,
                via,
                registration.is_active,
                registration,
                registration.course.shared_by(request.organisation),
                registration.course_id in available_course_ids,
            )

        rows = [row(r, "Individual") for r in individual] + [
            row(r, f"via {r.cohort.name}") for r in through_cohorts
        ]
        context = super().get_context_data()
        context["rows"] = sorted(rows, key=lambda row: row.course.title)
        return context


class LearnerHistoryPanel(HistoryPanel):
    model = Learner
    export_scope = "learner"
    refresh_events = (LEARNER_CHANGED,)
    empty_message = (
        "No history for this learner yet. Actions such as moving or "
        "deactivating them are recorded here."
    )

    def has_permission(self, request: HttpRequest) -> bool:
        """A learner's history spans every cohort they belong to, so it
        opens only for someone who may read the whole organisation's audit
        log, not for a cohort admin of one of those cohorts."""
        organisation = cast(Learner, self.instance).organisation
        return self.ctx.config.has_capability(request, self.capability, organisation)

    @property
    def scope_label(self) -> str:
        return cast(Learner, self.instance).user.display_name
