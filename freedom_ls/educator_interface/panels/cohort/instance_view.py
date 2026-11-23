"""The cohort page: its settings and overview stacks, tab set and instance view."""

from __future__ import annotations

from typing import cast

from freedom_ls.educator_interface.events import COHORT_CHANGED
from freedom_ls.educator_interface.forms import CohortForm
from freedom_ls.educator_interface.panels.cohort.actions import (
    EditCohortAction,
    cohort_state_actions,
)
from freedom_ls.educator_interface.panels.cohort.data_table_panels import (
    CohortCoursesPanel,
    CohortHistoryPanel,
    CohortLearnersPanel,
)
from freedom_ls.educator_interface.panels.cohort.panels import (
    CohortCourseCompletionPanel,
    CohortDetailsPanel,
    CohortNamePanel,
    CohortStaffPanel,
    CohortStatusPanel,
)
from freedom_ls.educator_interface.panels.cohort.report_panels import (
    CohortNeedsAttentionPanel,
    CohortReportStack,
)
from freedom_ls.educator_interface.panels.common.badges import inactive_badge
from freedom_ls.learner_management.models import Cohort
from freedom_ls.panel_framework.actions import PanelAction
from freedom_ls.panel_framework.panels import PanelStack, TabSet
from freedom_ls.panel_framework.views import InstanceView, StatusBadge

__all__ = [
    "CohortInstanceView",
    "CohortOverviewStack",
    "CohortSettingsStack",
    "CohortTabSet",
]


class CohortSettingsStack(PanelStack):
    """The cohort's Settings tab: one panel per job, so the name, the staff
    and the cohort's status each have their own card."""

    title = "Settings"
    refresh_events = (COHORT_CHANGED,)
    children = {
        "name": CohortNamePanel,
        "staff": CohortStaffPanel,
        "status": CohortStatusPanel,
    }


class CohortOverviewStack(PanelStack):
    title = "Overview"
    refresh_events = (COHORT_CHANGED,)
    children = {
        "details": CohortDetailsPanel,
        "completion": CohortCourseCompletionPanel,
        "attention": CohortNeedsAttentionPanel,
    }


class CohortTabSet(TabSet):
    title = "Cohort sections"
    children = {
        "overview": CohortOverviewStack,
        "learners": CohortLearnersPanel,
        "courses": CohortCoursesPanel,
        "report": CohortReportStack,
        "settings": CohortSettingsStack,
        "history": CohortHistoryPanel,
    }


class CohortInstanceView(InstanceView):
    panel = CohortTabSet
    header_refresh_events = (COHORT_CHANGED,)

    def get_status_badge(self) -> StatusBadge | None:
        return inactive_badge(cast(Cohort, self.instance).is_active)

    def get_actions(self) -> list[PanelAction]:
        # The actions keep their instance-level URLs; the Settings tab draws
        # their triggers, so the header draws none. The instance already
        # carries its own organisation, so the success URL needs nothing
        # from the request.
        cohort = cast(Cohort, self.instance)
        return [
            EditCohortAction(
                form_class=CohortForm,
                form_title=f"Edit {cohort}",
                instance=cohort,
                success_events=(COHORT_CHANGED,),
            ),
            *cohort_state_actions(),
        ]

    def get_header_actions(self) -> list[PanelAction]:
        return []
