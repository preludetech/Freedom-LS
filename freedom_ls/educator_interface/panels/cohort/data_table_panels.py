"""The cohort's Learners, Courses and History tab panels."""

from __future__ import annotations

from typing import cast

from panel_framework.actions import PanelAction
from panel_framework.panels import DataTablePanel

from django.db.models import QuerySet
from django.http import HttpRequest

from freedom_ls.educator_interface.events import (
    COHORT_CHANGED,
    REGISTRATION_CHANGED,
    STAFF_CHANGED,
)
from freedom_ls.educator_interface.panels.audit_log.data_table_panels import (
    HistoryPanel,
)
from freedom_ls.educator_interface.panels.audit_log.data_tables import (
    TargetedAuditLogEntryTable,
)
from freedom_ls.educator_interface.panels.cohort.actions import (
    AddExistingLearnersAction,
    AddLearnerToCohortAction,
    DeactivateCohortRegistrationAction,
    RegisterCohortForCourseAction,
)
from freedom_ls.educator_interface.panels.cohort.data_tables import (
    CohortCourseRegistrationDataTable,
)
from freedom_ls.educator_interface.panels.learner.actions import (
    ImportLearnersAction,
    MoveToCohortAction,
    RemoveFromCohortAction,
)
from freedom_ls.educator_interface.panels.learner.data_tables import (
    CohortLearnerDataTable,
)
from freedom_ls.learner_management.models import Cohort

__all__ = [
    "CohortCoursesPanel",
    "CohortHistoryPanel",
    "CohortLearnersPanel",
]


class CohortLearnersPanel(DataTablePanel):
    title = "Learners"
    data_table = CohortLearnerDataTable
    table_key = "learners"
    refresh_events = (COHORT_CHANGED,)

    def get_actions(self) -> list[PanelAction]:
        return [
            AddExistingLearnersAction(),
            AddLearnerToCohortAction(),
            ImportLearnersAction(),
            RemoveFromCohortAction(),
            MoveToCohortAction(),
        ]

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        # None offers the actions on every learner row; an inactive cohort
        # offers none.
        context["membership_param"] = "learner"
        context["membership_row_ids"] = (
            None if cast(Cohort, self.instance).is_active else set()
        )
        return context

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return (
            super().get_queryset(request).filter(cohortmembership__cohort=self.instance)
        )

    def get_export_scope_slug(self, request: HttpRequest) -> str:
        return cast(Cohort, self.instance).name

    def get_tab_count(self) -> int | None:
        # The table lists inactive learners too; the tab counts current ones.
        return self.get_queryset(self.request).filter(is_active=True).count()


class CohortCoursesPanel(DataTablePanel):
    title = "Courses"
    data_table = CohortCourseRegistrationDataTable
    table_key = "cohort_courses"
    refresh_events = (COHORT_CHANGED, REGISTRATION_CHANGED)

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).filter(cohort=self.instance)

    def get_actions(self) -> list[PanelAction]:
        # Deactivate renders per row, not in the footer: the registration cell
        # reads its URL from row_action_urls.
        return [RegisterCohortForCourseAction(), DeactivateCohortRegistrationAction()]

    def get_tab_count(self) -> int | None:
        return self.get_queryset(self.request).filter(is_active=True).count()


class CohortHistoryPanel(HistoryPanel):
    model = Cohort
    data_table = TargetedAuditLogEntryTable
    # A role assigned from the Educators panel is a cohort entry too.
    refresh_events = (COHORT_CHANGED, STAFF_CHANGED)
    export_scope = "cohort"
    empty_message = "No history for this cohort yet. Actions such as adding learners or registering it for a course are recorded here."

    @property
    def scope_label(self) -> str:
        return cast(Cohort, self.instance).name
