"""Panel actions on a cohort that need more than the generic framework ones."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import UUID

from django import forms
from django.db import transaction
from django.db.models import Model
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string

from freedom_ls.educator_interface.events import COHORT_CHANGED, LEARNER_CHANGED
from freedom_ls.educator_interface.forms import (
    CohortCourseRegistrationForm,
    LearnerNameForm,
)
from freedom_ls.learner_management.learner_actions import (
    deactivate_learner,
    reactivate_learner,
    remove_from_cohort,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    Learner,
)
from freedom_ls.learner_management.queries import (
    cohort_course_count,
    cohort_is_empty,
    cohort_learner_count,
    cohorts_visible_to,
    courses_losing_access,
    learners_visible_to,
    members_keeping_access,
)
from freedom_ls.learner_management.utils import (
    register_cohort_for_course,
    unregister_cohort_from_course,
)
from freedom_ls.organisations.utils import get_default_organisation
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
from freedom_ls.panel_framework.events import build_hx_trigger

if TYPE_CHECKING:
    from freedom_ls.educator_interface.views import OrganisationScopedRequest


def _uuid_param(request: HttpRequest, name: str) -> UUID:
    """A UUID the action's trigger sent along: from the form on a submit, from
    the query string otherwise. A missing or malformed value is a 404."""
    params = request.POST if request.method == "POST" else request.GET
    try:
        return UUID(params.get(name, ""))
    except ValueError:
        raise Http404(f"No such {name}") from None


def inactive_cohort_response(request: HttpRequest, cohort: Cohort) -> HttpResponse:
    """The 422 fragment for a change aimed at an inactive cohort."""
    return render(
        request,
        "educator_interface/modal/cohort_inactive.html",
        {"cohort": cohort},
        status=422,
    )


def cohort_not_empty_sentence(cohort: Cohort) -> str:
    """Why a cohort cannot be deleted, counting everything deletion would
    cascade away: removed learners and inactive registrations included.
    Empty for an empty cohort, so one call tells a caller both things."""
    learners = cohort.cohortmembership_set.count()
    registrations = cohort.course_registrations.count()
    parts = []
    if learners:
        parts.append(count_noun(Learner, learners))
    if registrations:
        parts.append(
            count_phrase(registrations, "course registration", "course registrations")
        )
    if not parts:
        return ""
    return (
        f"{cohort} can't be deleted while it has {join_prose(parts)}, counting "
        "removed learners and inactive registrations."
    )


class RequiresActiveCohortMixin(PanelAction):
    """Offers an action only while the cohort is active, and refuses a submit
    for an inactive one. Declared on PanelAction so the overrides type-check;
    list it before the action it guards in the bases."""

    def is_offered(self, ctx: PanelContext) -> bool:
        return cast(Cohort, ctx.instance).is_active

    def refuse_inactive(self, ctx: PanelContext) -> HttpResponse:
        return inactive_cohort_response(ctx.request, cast(Cohort, ctx.instance))

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        if not cast(Cohort, ctx.instance).is_active:
            return self.refuse_inactive(ctx)
        return self.handle_active_submit(ctx)

    def handle_active_submit(self, ctx: PanelContext) -> HttpResponse:
        """The submit once the cohort is known to be active: the next
        handle_submit in the MRO. An action with no base submit of its own
        overrides this, never handle_submit, so the guard above stays the
        one place the refusal lives."""
        return super().handle_submit(ctx)


class EditCohortAction(RequiresActiveCohortMixin, EditAction):
    """Edit, offered only while the cohort is active."""


class EditLearnerNameAction(EditAction):
    """Edit the learner's first and last name, which live on their user."""

    label = "Edit name"
    action_name = "edit_name"

    def __init__(self, learner: Learner) -> None:
        super().__init__(
            form_class=LearnerNameForm,
            form_title=f"Edit {learner.user.display_name}",
            instance=learner.user,
            success_events=(LEARNER_CHANGED,),
        )
        self._learner = learner

    def get_form(
        self, request: HttpRequest, instance: Model | None = None
    ) -> forms.ModelForm:
        # The page's instance is the learner; the form edits their user.
        return super().get_form(request, self._instance)

    def event_instance(self, form: forms.ModelForm) -> Model:
        return self._learner


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
        context["not_empty_sentence"] = cohort_not_empty_sentence(cohort)
        context["is_empty"] = not context["not_empty_sentence"]
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

    def _blocked_context(
        self, ctx: PanelContext, cohort: Cohort, reason: str
    ) -> dict[str, object]:
        return self._confirmation_context(
            ctx, cohort, cascade_summary=[], blocked_reason=reason
        )

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        cohort = cast(Cohort, ctx.instance)
        reason = cohort_not_empty_sentence(cohort)
        if reason:
            return self._blocked_context(ctx, cohort, reason)
        return super().get_context_data(ctx)

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        with transaction.atomic():
            # Lock the cohort so a membership added between this check and the
            # delete either lands first and is refused here, or waits and then
            # fails on the missing cohort. A cohort another request deleted
            # while this one waited is a 404, which the action route answers
            # with its "unavailable" fragment.
            cohort = get_object_or_404(
                Cohort.objects.select_for_update(), pk=cast(Cohort, ctx.instance).pk
            )
            reason = cohort_not_empty_sentence(cohort)
            if reason:
                html = render_to_string(
                    self.template_name,
                    self._blocked_context(ctx, cohort, reason),
                    request=ctx.request,
                )
                return HttpResponse(html, status=422)
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


class LearnerStateAction(PanelAction):
    """Moves a learner to `target_state`, after confirmation."""

    trigger_template_name = "panel_framework/partials/modal_trigger.html"
    variant = "secondary"
    capability = "freedom_ls_learner_management.change_learner"
    target_state: bool

    def perform(self, learner: Learner) -> bool:
        raise NotImplementedError

    def is_offered(self, ctx: PanelContext) -> bool:
        return cast(Learner, ctx.instance).is_active != self.target_state

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        learner = cast(Learner, ctx.instance)
        context = super().get_context_data(ctx)
        context["learner"] = learner
        context["on_default_organisation"] = (
            learner.organisation_id == get_default_organisation(learner.site).pk
        )
        return context

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        learner = cast(Learner, ctx.instance)
        if not self.perform(learner):
            return render(
                ctx.request,
                "educator_interface/modal/learner_already_in_state.html",
                {"learner": learner, "state": self.label},
                status=422,
            )
        # The header's badge and actions change, so the page re-renders in
        # full and no domain event is sent.
        return navigation_response(ctx.page_url)


class DeactivateLearnerAction(LearnerStateAction):
    label = "Deactivate"
    action_name = "deactivate"
    target_state = False
    template_name = "educator_interface/modal/deactivate_learner_confirmation.html"

    def perform(self, learner: Learner) -> bool:
        return deactivate_learner(learner)


class ReactivateLearnerAction(LearnerStateAction):
    label = "Reactivate"
    action_name = "reactivate"
    target_state = True
    template_name = "educator_interface/modal/reactivate_learner_confirmation.html"

    def perform(self, learner: Learner) -> bool:
        return reactivate_learner(learner)


def learner_state_actions() -> list[PanelAction]:
    """Both state actions; `is_offered` picks which one renders."""
    return [DeactivateLearnerAction(), ReactivateLearnerAction()]


KEEPING_NAMES_SHOWN = 10


class UnregisterCohortFromCourseAction(RequiresActiveCohortMixin, PanelAction):
    """Withdraws one of the cohort's active course registrations, after
    confirmation. The registration travels as a `registration` parameter, so
    the action resolves on the courses tab and renders per row there, never
    as a footer button."""

    label = "Unregister"
    action_name = "unregister"
    variant = "secondary"
    renders_in_footer = False
    capability = "freedom_ls_learner_management.change_cohortcourseregistration"
    trigger_template_name = "panel_framework/partials/modal_trigger.html"
    template_name = "educator_interface/modal/unregister_confirmation.html"

    def _registration(self, ctx: PanelContext) -> CohortCourseRegistration:
        return get_object_or_404(
            cast(Cohort, ctx.instance).course_registrations.select_related("course"),
            pk=_uuid_param(ctx.request, "registration"),
            is_active=True,
        )

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        cohort = cast(Cohort, ctx.instance)
        registration = self._registration(ctx)
        keeping = list(members_keeping_access(registration))
        member_count = cohort_learner_count(cohort)
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

    def handle_active_submit(self, ctx: PanelContext) -> HttpResponse:
        unregister_cohort_from_course(self._registration(ctx))
        # The courses tab, its count and the header's course stat all
        # re-render, which a panel refresh alone could not do for the header.
        return navigation_response(ctx.page_url)


class MembershipAction(PanelAction):
    """A change to one learner's membership of one cohort, after confirmation.

    The action resolves on the learner page, where the cohort travels as a
    `cohort` parameter, and on the cohort page, where the learner travels as
    a `learner` parameter. It renders per row, never as a footer button.
    """

    variant = "secondary"
    renders_in_footer = False
    trigger_template_name = "panel_framework/partials/modal_trigger.html"

    def perform(self, learner: Learner, cohort: Cohort) -> bool:
        raise NotImplementedError

    def _cohort(self, ctx: PanelContext) -> Cohort:
        if isinstance(ctx.instance, Cohort):
            return ctx.instance
        scoped = cast("OrganisationScopedRequest", ctx.request)
        return get_object_or_404(
            cohorts_visible_to(scoped.user, scoped.organisation),
            pk=_uuid_param(ctx.request, "cohort"),
        )

    def _pair(self, ctx: PanelContext) -> tuple[Learner, Cohort]:
        if isinstance(ctx.instance, Cohort):
            scoped = cast("OrganisationScopedRequest", ctx.request)
            learner = get_object_or_404(
                learners_visible_to(
                    scoped.user, scoped.organisation, include_removed=True
                ),
                pk=_uuid_param(ctx.request, "learner"),
            )
            return learner, ctx.instance
        return cast(Learner, ctx.instance), self._cohort(ctx)

    def permission_object(self, ctx: PanelContext) -> Model | None:
        # Rendering asks has_permission before any row names a cohort, so the
        # capability is asked about the page's own object until a submit or a
        # fragment names the cohort.
        if (
            isinstance(ctx.instance, Cohort)
            or "cohort" in ctx.request.GET
            or "cohort" in ctx.request.POST
        ):
            return self._cohort(ctx)
        return ctx.scope_object()

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        learner, cohort = self._pair(ctx)
        if not cohort.is_active:
            return inactive_cohort_response(ctx.request, cohort)
        self.perform(learner, cohort)
        ids = [str(learner.pk), str(cohort.pk)]
        response = HttpResponse(status=204)
        response["HX-Trigger"] = build_hx_trigger(
            {LEARNER_CHANGED: ids, COHORT_CHANGED: ids}, close_modal=True
        )
        return response


class RemoveFromCohortAction(MembershipAction):
    label = "Remove from cohort"
    action_name = "remove_from_cohort"
    capability = "freedom_ls_learner_management.delete_cohortmembership"
    template_name = "educator_interface/modal/remove_from_cohort_confirmation.html"

    def perform(self, learner: Learner, cohort: Cohort) -> bool:
        return remove_from_cohort(learner, cohort)

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        learner, cohort = self._pair(ctx)
        if isinstance(ctx.instance, Cohort):
            other_side = {"name": "learner", "value": str(learner.pk)}
        else:
            other_side = {"name": "cohort", "value": str(cohort.pk)}
        context = super().get_context_data(ctx)
        context.update(
            {
                "learner": learner,
                "cohort": cohort,
                "losing_courses": join_prose(
                    [str(course) for course in courses_losing_access(learner, cohort)]
                ),
                "other_side": other_side,
                "confirm_url": self.get_action_url(ctx),
            }
        )
        return context


def cohort_state_actions() -> list[PanelAction]:
    """Both state actions; `is_offered` picks which one renders."""
    return [DeactivateCohortAction(), ReactivateCohortAction()]
