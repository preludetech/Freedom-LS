"""Panel actions on a cohort that need more than the generic framework ones."""

from __future__ import annotations

from typing import cast

from django.http import HttpResponse
from django.shortcuts import render

from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    Learner,
)
from freedom_ls.learner_management.queries import (
    cohort_course_count,
    cohort_is_empty,
)
from freedom_ls.panel_framework.actions import (
    EditAction,
    PanelAction,
    count_noun,
    join_prose,
    navigation_response,
)
from freedom_ls.panel_framework.context import PanelContext


def cohort_not_empty_sentence(cohort: Cohort) -> str:
    """Why a cohort cannot be deleted, counting everything deletion would
    cascade away: removed learners and inactive registrations included."""
    learners = cohort.cohortmembership_set.count()
    registrations = cohort.course_registrations.count()
    counts = join_prose(
        [
            count_noun(Learner, learners),
            count_noun(CohortCourseRegistration, registrations),
        ]
    )
    return (
        f"{cohort} can't be deleted while it has {counts}, counting removed "
        "learners and inactive registrations."
    )


class RequiresActiveCohortMixin(PanelAction):
    """Offers an action only while the cohort is active, and refuses a submit
    for an inactive one. Declared on PanelAction so the overrides type-check;
    list it before the action it guards in the bases."""

    def is_offered(self, ctx: PanelContext) -> bool:
        return cast(Cohort, ctx.instance).is_active

    def refuse_inactive(self, ctx: PanelContext) -> HttpResponse:
        return render(
            ctx.request,
            "educator_interface/modal/cohort_inactive.html",
            {"cohort": ctx.instance},
            status=422,
        )

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        if not cast(Cohort, ctx.instance).is_active:
            return self.refuse_inactive(ctx)
        return super().handle_submit(ctx)


class EditCohortAction(RequiresActiveCohortMixin, EditAction):
    """Edit, offered only while the cohort is active."""


class CohortStateAction(PanelAction):
    """Moves a cohort to `target_state`, after confirmation."""

    trigger_template_name = "panel_framework/partials/modal_trigger.html"
    variant = "secondary"
    capability = "freedom_ls_learner_management.change_cohort"
    target_state: bool

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        cohort = cast(Cohort, ctx.instance)
        context = super().get_context_data(ctx)
        context["cohort"] = cohort
        context["cohort_course_count"] = cohort_course_count(cohort)
        context["is_empty"] = cohort_is_empty(cohort)
        context["not_empty_sentence"] = (
            "" if context["is_empty"] else cohort_not_empty_sentence(cohort)
        )
        return context

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        cohort = cast(Cohort, ctx.instance)
        cohort.is_active = self.target_state
        cohort.save(update_fields=["is_active", "updated_at"])
        # The page re-renders in full, header included, so no domain event is
        # sent: the panels would only refetch themselves and then be replaced.
        return navigation_response(ctx.page_url)


class DeactivateCohortAction(RequiresActiveCohortMixin, CohortStateAction):
    label = "Deactivate"
    action_name = "deactivate"
    target_state = False
    template_name = "educator_interface/modal/deactivate_confirmation.html"


class ReactivateCohortAction(CohortStateAction):
    label = "Reactivate"
    action_name = "reactivate"
    target_state = True
    template_name = "educator_interface/modal/reactivate_confirmation.html"

    def is_offered(self, ctx: PanelContext) -> bool:
        return not cast(Cohort, ctx.instance).is_active

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        if cast(Cohort, ctx.instance).is_active:
            return render(
                ctx.request,
                "educator_interface/modal/cohort_already_active.html",
                {"cohort": ctx.instance},
                status=422,
            )
        return super().handle_submit(ctx)


def cohort_state_actions() -> list[PanelAction]:
    """Both state actions; `is_offered` picks which one renders."""
    return [DeactivateCohortAction(), ReactivateCohortAction()]
