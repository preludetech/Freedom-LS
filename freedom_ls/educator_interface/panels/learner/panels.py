"""The learner page's detail, name, account and courses panels."""

from __future__ import annotations

from typing import cast

from django.http import HttpRequest

from freedom_ls.educator_interface.events import (
    LEARNER_CHANGED,
    REGISTRATION_CHANGED,
)
from freedom_ls.educator_interface.panels.common.badges import learner_status_badge
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.educator_interface.panels.learner.actions import (
    EditLearnerNameAction,
    RegisterLearnerForCourseAction,
    ResendSetupEmailAction,
    learner_state_actions,
)
from freedom_ls.educator_interface.panels.learner.quick_view import (
    visible_registrations_with_progress,
)
from freedom_ls.educator_interface.panels.learner.quiz_attempt import (
    openable_sitting_ids,
)
from freedom_ls.learner_management.models import Learner
from freedom_ls.learner_management.queries import learner_status
from freedom_ls.panel_framework.actions import PanelAction
from freedom_ls.panel_framework.panels import InstanceDetailsPanel, Panel
from freedom_ls.reports.gather import gather_learner_course_details

__all__ = [
    "LearnerAccountPanel",
    "LearnerCoursesPanel",
    "LearnerDetailsPanel",
    "LearnerNamePanel",
]


class LearnerDetailsPanel(InstanceDetailsPanel):
    model = Learner
    refresh_events = (LEARNER_CHANGED,)

    def get_rows(self) -> list[dict[str, object]]:
        learner = cast(Learner, self.instance)
        return [
            self.detail_row("Name", learner.user.display_name),
            self.detail_row("Email", learner.user.email),
            self.detail_row("Status", learner_status_badge(learner), "badge"),
            self.detail_row("Date added", learner.created_at, "date"),
        ]


class LearnerNamePanel(Panel):
    """The learner's first and last name as fields with Save, posted inline
    to the edit action, as the cohort's Name panel is. Shown only to someone
    who may change the name."""

    model = Learner
    title = "Name"
    template_name = "educator_interface/panels/learner_name.html"
    refresh_events = (LEARNER_CHANGED,)

    def has_permission(self, request: HttpRequest) -> bool:
        return super().has_permission(request) and bool(self.available_actions)

    def get_actions(self) -> list[PanelAction]:
        return [EditLearnerNameAction(cast(Learner, self.instance))]

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        context["rename"] = self.available_actions[0].get_context_data(self.ctx)
        return context


class LearnerAccountPanel(Panel):
    """The learner's account: whether it is set up and active, with Resend
    setup email and Deactivate or Reactivate in the footer. Shown to anyone
    who may take one of those actions."""

    model = Learner
    title = "Account"
    template_name = "educator_interface/panels/learner_account.html"
    refresh_events = (LEARNER_CHANGED,)

    def has_permission(self, request: HttpRequest) -> bool:
        return super().has_permission(request) and bool(self.available_actions)

    def get_actions(self) -> list[PanelAction]:
        return [ResendSetupEmailAction(), *learner_state_actions()]

    def get_context_data(self) -> dict[str, object]:
        learner = cast(Learner, self.instance)
        context = super().get_context_data()
        context["learner"] = learner
        context["status"] = learner_status(learner)
        return context


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
        visible = visible_registrations_with_progress(learner, request)
        registrations = [
            entry.registration
            for entry in sorted(visible, key=lambda entry: entry.course.title)
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
        # One check for every attempt on the tab, reusing the registrations
        # already loaded above.
        context["openable_sitting_ids"] = openable_sitting_ids(
            request,
            [
                attempt.form_progress_id
                for detail in details
                for quiz in detail.quiz_results
                for attempt in quiz.attempts
            ],
            shown_registrations={learner.pk: visible},
        )
        return context
