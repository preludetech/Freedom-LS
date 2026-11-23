"""The cohort's details, course completion, name, staff and status panels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from django.db.models import Count, F, Q
from django.http import HttpRequest

from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.events import (
    COHORT_CHANGED,
    REGISTRATION_CHANGED,
    STAFF_CHANGED,
)
from freedom_ls.educator_interface.forms import CohortForm
from freedom_ls.educator_interface.panels.cohort.actions import (
    DeleteEmptyCohortAction,
    EditCohortAction,
    cohort_not_empty_sentence,
    cohort_state_actions,
)
from freedom_ls.educator_interface.panels.common.badges import active_status_badge
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.educator_interface.panels.staff.actions import (
    AddStaffMemberToCohortAction,
    ChangeRoleAction,
    RemoveStaffFromCohortAction,
    roles_grantable_on,
)
from freedom_ls.educator_interface.paths import interface_path
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.models import Cohort
from freedom_ls.learner_management.queries import (
    ASSIGN_COHORT_VIEWER,
    CHANGE_COHORT,
    cohort_counts,
    cohort_educators,
)
from freedom_ls.panel_framework.actions import PanelAction
from freedom_ls.panel_framework.panels import InstanceDetailsPanel, Panel

__all__ = [
    "CohortCourseCompletionPanel",
    "CohortDetailsPanel",
    "CohortNamePanel",
    "CohortStaffPanel",
    "CohortStatusPanel",
    "CourseCompletion",
]


class CohortDetailsPanel(InstanceDetailsPanel):
    model = Cohort
    refresh_events = (COHORT_CHANGED,)

    def get_rows(self) -> list[dict[str, object]]:
        cohort = cast(Cohort, self.instance)
        counts = cohort_counts(cohort)
        return [
            self.detail_row("Name", cohort.name),
            self.detail_row("Status", active_status_badge(cohort.is_active), "badge"),
            self.detail_row("Created", cohort.created_at, "date"),
            self.detail_row("Learners", counts.learners),
            self.detail_row("Courses", counts.courses),
        ]


@dataclass(frozen=True)
class CourseCompletion:
    """How far one course registration's current members have got."""

    course: Course
    completed_count: int
    record_count: int
    percentage: int
    shared_by: str | None = None

    @property
    def detail(self) -> str:
        """The muted line under the course title: who shares the course when
        another organisation owns it, then how many members have completed."""
        progress = f"{self.completed_count} of {self.record_count} completed"
        return (
            f"Shared by {self.shared_by} · {progress}" if self.shared_by else progress
        )


class CohortCourseCompletionPanel(Panel):
    model = Cohort
    title = "Course completion"
    template_name = "educator_interface/panels/cohort_course_completion.html"
    refresh_events = (COHORT_CHANGED, REGISTRATION_CHANGED)

    def get_context_data(self) -> dict[str, object]:
        cohort = cast(Cohort, self.instance)
        # Course progress records minted for members who have since been
        # deactivated or have left the cohort are kept for ever, so the counts are
        # narrowed to current, active members or they would disagree with the
        # Learners tab.
        current_member = Q(
            course_progress_records__learner__is_active=True,
            course_progress_records__learner__cohortmembership__cohort_id=F(
                "cohort_id"
            ),
        )
        registrations = (
            cohort.course_registrations.filter(is_active=True)
            .select_related("course")
            .prefetch_related("course__organisations")
            .annotate(
                record_count=Count(
                    "course_progress_records", filter=current_member, distinct=True
                ),
                completed_count=Count(
                    "course_progress_records",
                    filter=current_member
                    & Q(course_progress_records__completed_time__isnull=False),
                    distinct=True,
                ),
            )
            .order_by("course__title")
        )
        context = super().get_context_data()
        context["completions"] = [
            CourseCompletion(
                course=registration.course,
                completed_count=registration.completed_count,
                record_count=registration.record_count,
                percentage=(
                    registration.completed_count * 100 // registration.record_count
                    if registration.record_count
                    else 0
                ),
                shared_by=registration.course.shared_by(
                    cast(OrganisationScopedRequest, self.request).organisation
                ),
            )
            for registration in registrations
        ]
        return context


class CohortNamePanel(Panel):
    """The cohort's name as a field with Save, posted inline to the edit
    action. Hidden when the edit action is not available, as on an inactive
    cohort."""

    title = "Name"
    capability = CHANGE_COHORT
    template_name = "educator_interface/panels/cohort_name.html"
    refresh_events = (COHORT_CHANGED,)

    def get_actions(self) -> list[PanelAction]:
        cohort = cast(Cohort, self.instance)
        return [
            EditCohortAction(
                form_class=CohortForm,
                form_title=f"Edit {cohort}",
                instance=cohort,
                success_events=(COHORT_CHANGED,),
            )
        ]

    def is_shown(self) -> bool:
        return super().is_shown() and bool(self.available_actions)

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        context["rename"] = self.available_actions[0].get_context_data(self.ctx)
        return context


class CohortStaffPanel(Panel):
    """The cohort's staff: Add staff member in the header, then one row per
    person with their role and Change role and Remove from cohort for each
    cohort role the viewer may give. A cohort admin who cannot change the
    cohort still gets this panel, since they may give cohort roles on it."""

    title = "Staff"
    template_name = "educator_interface/panels/cohort_staff.html"
    refresh_events = (COHORT_CHANGED, STAFF_CHANGED)

    def has_permission(self, request: HttpRequest) -> bool:
        cohort = cast(Cohort, self.instance)
        return can(request.user, CHANGE_COHORT, cohort) or can(
            request.user, ASSIGN_COHORT_VIEWER, cohort
        )

    def get_actions(self) -> list[PanelAction]:
        return [
            AddStaffMemberToCohortAction(),
            ChangeRoleAction(),
            RemoveStaffFromCohortAction(),
        ]

    def get_context_data(self) -> dict[str, object]:
        cohort = cast(Cohort, self.instance)
        context = super().get_context_data()
        by_name = {action.action_name: action for action in self.available_actions}
        remove = by_name.get("remove_staff_from_cohort")
        change = by_name.get("change_role")
        context["add_staff"] = by_name.get("add_staff_member")
        context["remove_from_cohort_url"] = (
            remove.get_action_url(self.ctx) if remove else ""
        )
        context["change_role_url"] = change.get_action_url(self.ctx) if change else ""
        context["educators"] = cohort_educators(cohort)
        context["grantable"] = roles_grantable_on(self.request, cohort)
        return context


class CohortStatusPanel(Panel):
    """Whether the cohort is active, with Deactivate or Reactivate and
    Delete in the footer."""

    title = "Status"
    capability = CHANGE_COHORT
    template_name = "educator_interface/panels/cohort_status.html"
    refresh_events = (COHORT_CHANGED,)

    def get_actions(self) -> list[PanelAction]:
        cohort = cast(Cohort, self.instance)
        return [
            *cohort_state_actions(),
            DeleteEmptyCohortAction(
                success_url=interface_path(cohort.organisation, "cohorts"),
            ),
        ]

    def get_context_data(self) -> dict[str, object]:
        cohort = cast(Cohort, self.instance)
        context = super().get_context_data()
        context["cohort"] = cohort
        context["not_empty_sentence"] = cohort_not_empty_sentence(cohort)
        return context
