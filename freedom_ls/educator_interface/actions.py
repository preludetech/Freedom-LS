"""Panel actions on a cohort that need more than the generic framework ones."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from django import forms
from django.db import transaction
from django.db.models import Model
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string

from freedom_ls.educator_interface.forms import CohortCourseRegistrationForm
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    Learner,
)
from freedom_ls.learner_management.queries import (
    cohort_course_count,
    cohort_is_empty,
    members_keeping_access,
)
from freedom_ls.learner_management.utils import (
    register_cohort_for_course,
    unregister_cohort_from_course,
)
from freedom_ls.panel_framework.actions import (
    DeleteAction,
    EditAction,
    FormPanelAction,
    PanelAction,
    count_noun,
    count_phrase,
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
            count_phrase(registrations, "course registration", "course registrations"),
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


class DeleteEmptyCohortAction(DeleteAction):
    """Deletes a cohort that has no memberships and no course registrations.

    A cohort that is not empty is neither offered the action nor allowed to
    submit it: deletion would cascade away removed learners' memberships and
    inactive registrations, which nobody sees on the page.
    """

    def is_offered(self, ctx: PanelContext) -> bool:
        return cohort_is_empty(cast(Cohort, ctx.instance))

    def _refuse_not_empty(self, ctx: PanelContext, cohort: Cohort) -> HttpResponse:
        html = render_to_string(
            self.template_name,
            self._confirmation_context(
                ctx,
                cohort,
                cascade_summary=[],
                blocked_reason=cohort_not_empty_sentence(cohort),
            ),
            request=ctx.request,
        )
        return HttpResponse(html, status=422)

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        cohort = cast(Cohort, ctx.instance)
        if not cohort_is_empty(cohort):
            return self._confirmation_context(
                ctx,
                cohort,
                cascade_summary=[],
                blocked_reason=cohort_not_empty_sentence(cohort),
            )
        return super().get_context_data(ctx)

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        with transaction.atomic():
            # Lock the cohort so a membership added between this check and the
            # delete either lands first and is refused here, or waits and then
            # fails on the missing cohort.
            cohort = Cohort.objects.select_for_update().get(
                pk=cast(Cohort, ctx.instance).pk
            )
            if not cohort_is_empty(cohort):
                return self._refuse_not_empty(ctx, cohort)
            return super().handle_submit(ctx)


class RegisterCohortForCourseAction(RequiresActiveCohortMixin, FormPanelAction):
    """Registers the cohort for a course it holds no active registration for."""

    label = "Register"
    action_name = "register"
    capability = "freedom_ls_learner_management.add_cohortcourseregistration"
    submit_buttons = [
        {"label": "Register", "variant": "primary", "loading_text": "Registering..."}
    ]
    _cohort: Cohort
    _page_url: str

    def _bind(self, ctx: PanelContext) -> None:
        self._cohort = cast(Cohort, ctx.instance)
        self._page_url = ctx.page_url
        self.form_title = f"Register {self._cohort} for a course"

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        self._bind(ctx)
        return super().get_context_data(ctx)

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        self._bind(ctx)
        return super().handle_submit(ctx)

    def get_form(
        self, request: HttpRequest, instance: Model | None = None
    ) -> forms.ModelForm:
        # On a POST, instance is the cohort, which must never reach a
        # registration form.
        data = request.POST if request.method == "POST" else None
        return CohortCourseRegistrationForm(data, cohort=self._cohort)

    def form_valid(self, request: HttpRequest, form: forms.ModelForm) -> HttpResponse:
        register_cohort_for_course(self._cohort, form.cleaned_data["course"])
        # The courses tab, its count and the header's course stat all
        # re-render, which a panel refresh alone could not do for the header.
        return navigation_response(self._page_url)


KEEPING_NAMES_SHOWN = 10


class UnregisterCohortFromCourseAction(RequiresActiveCohortMixin, PanelAction):
    """Withdraws one of the cohort's active course registrations, after
    confirmation. The registration travels as a `registration` parameter, so
    the action resolves on the courses tab and never renders as a footer
    button."""

    label = "Unregister"
    action_name = "unregister"
    variant = "secondary"
    capability = "freedom_ls_learner_management.change_cohortcourseregistration"
    trigger_template_name = "panel_framework/partials/modal_trigger.html"
    template_name = "educator_interface/modal/unregister_confirmation.html"

    def _registration(self, ctx: PanelContext) -> CohortCourseRegistration:
        params = ctx.request.POST if ctx.request.method == "POST" else ctx.request.GET
        try:
            registration_pk = UUID(params.get("registration", ""))
        except ValueError:
            raise Http404("No such registration") from None
        return get_object_or_404(
            cast(Cohort, ctx.instance).course_registrations.select_related("course"),
            pk=registration_pk,
            is_active=True,
        )

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        cohort = cast(Cohort, ctx.instance)
        registration = self._registration(ctx)
        keeping = list(members_keeping_access(registration))
        member_count = cohort.cohortmembership_set.filter(
            learner__is_active=True
        ).count()
        names = [learner.user.display_name for learner in keeping[:KEEPING_NAMES_SHOWN]]
        if len(keeping) > KEEPING_NAMES_SHOWN:
            names.append(f"{len(keeping) - KEEPING_NAMES_SHOWN} more")
        context = super().get_context_data(ctx)
        context.update(
            {
                "cohort": cohort,
                "registration": registration,
                "course": registration.course,
                "losing_count": member_count - len(keeping),
                "losing_phrase": count_noun(Learner, member_count - len(keeping)),
                "keeping_names": join_prose(names),
                "confirm_url": self.get_action_url(ctx),
            }
        )
        return context

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        if not cast(Cohort, ctx.instance).is_active:
            return self.refuse_inactive(ctx)
        unregister_cohort_from_course(self._registration(ctx))
        # The courses tab, its count and the header's course stat all
        # re-render, which a panel refresh alone could not do for the header.
        return navigation_response(ctx.page_url)


def cohort_state_actions() -> list[PanelAction]:
    """Both state actions; `is_offered` picks which one renders."""
    return [DeactivateCohortAction(), ReactivateCohortAction()]
