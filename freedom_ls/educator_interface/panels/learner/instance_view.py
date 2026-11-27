"""The learner page: its tabs, stacks and header."""

from __future__ import annotations

from typing import cast

from panel_framework.actions import PanelAction
from panel_framework.panels import PanelStack, TabSet
from panel_framework.views import InstanceView, StatusBadge

from freedom_ls.educator_interface.events import LEARNER_CHANGED
from freedom_ls.educator_interface.panels.common.badges import learner_status_badge
from freedom_ls.educator_interface.panels.learner.actions import (
    AddToCohortAction,
    EditLearnerNameAction,
    RegisterLearnerForCourseAction,
    ResendSetupEmailAction,
    learner_state_actions,
)
from freedom_ls.educator_interface.panels.learner.data_table_panels import (
    LearnerCohortsPanel,
    LearnerHistoryPanel,
    LearnerRegistrationsPanel,
)
from freedom_ls.educator_interface.panels.learner.messages import (
    LearnerMessagesStack,
)
from freedom_ls.educator_interface.panels.learner.panels import (
    LearnerAccountPanel,
    LearnerCoursesPanel,
    LearnerDetailsPanel,
    LearnerNamePanel,
)
from freedom_ls.learner_management.models import Learner
from freedom_ls.learner_management.queries import LearnerStatus, learner_status

__all__ = [
    "LearnerCoursesStack",
    "LearnerInstanceView",
    "LearnerOverviewStack",
    "LearnerSettingsStack",
    "LearnerTabSet",
    "learner_actions",
    "settings_actions",
]


class LearnerOverviewStack(PanelStack):
    """No refresh events of its own: each child re-fetches itself on
    LEARNER_CHANGED, so a stack refresh would render them all twice."""

    title = "Overview"
    children = {
        "details": LearnerDetailsPanel,
        "cohorts": LearnerCohortsPanel,
        "registrations": LearnerRegistrationsPanel,
    }


class LearnerCoursesStack(PanelStack):
    title = "Courses"
    refresh_events = (LEARNER_CHANGED,)
    children = {"courses": LearnerCoursesPanel}


class LearnerSettingsStack(PanelStack):
    """The learner's Settings tab: the actions with no home of their own,
    one panel per job. Add to cohort lives on the Cohorts panel and Register
    for a course on the Courses tab, beside what they change."""

    model = Learner
    title = "Settings"
    children = {"name": LearnerNamePanel, "account": LearnerAccountPanel}


def settings_actions(learner: Learner) -> list[PanelAction]:
    """The Settings tab's actions on one learner, in the order it offers
    them: those with no home beside the thing they change."""
    return [
        EditLearnerNameAction(learner),
        ResendSetupEmailAction(),
        *learner_state_actions(),
    ]


def learner_actions(learner: Learner) -> list[PanelAction]:
    """Every action on one learner, so each keeps its instance-level URL.
    The Settings tab, the Cohorts panel and the Courses tab draw the
    triggers; the page header draws none."""
    return [
        *settings_actions(learner),
        AddToCohortAction(),
        RegisterLearnerForCourseAction(),
    ]


class LearnerTabSet(TabSet):
    title = "Learner sections"
    children = {
        "overview": LearnerOverviewStack,
        "courses": LearnerCoursesStack,
        "messages": LearnerMessagesStack,
        "settings": LearnerSettingsStack,
        "history": LearnerHistoryPanel,
    }


class LearnerInstanceView(InstanceView):
    panel = LearnerTabSet
    header_refresh_events = (LEARNER_CHANGED,)

    def get_status_badge(self) -> StatusBadge | None:
        """Active is the default state, so only Pending and Inactive show."""
        learner = cast(Learner, self.instance)
        if learner_status(learner) is LearnerStatus.ACTIVE:
            return None
        return learner_status_badge(learner)

    def get_subtitle(self) -> str:
        return cast(Learner, self.instance).user.email

    def get_actions(self) -> list[PanelAction]:
        # The actions keep their instance-level URLs; the Settings tab
        # draws their triggers, so the header draws none.
        return learner_actions(cast(Learner, self.instance))

    def get_header_actions(self) -> list[PanelAction]:
        return []
