"""The actions on a single cohort."""

from __future__ import annotations

from typing import cast

from panel_framework.actions import (
    ConfirmAction,
    DeleteAction,
    EditAction,
    FormPanelAction,
    PanelAction,
    count_noun,
    count_phrase,
    current_page_within,
    join_prose,
    navigation_response,
)
from panel_framework.context import PanelContext

from django import forms
from django.db import transaction
from django.db.models import Model, QuerySet
from django.http import (
    HttpResponse,
)
from django.shortcuts import get_object_or_404

from freedom_ls.accounts.models import User
from freedom_ls.educator_interface.forms import (
    CohortCourseRegistrationForm,
    LearnerPickerForm,
)
from freedom_ls.educator_interface.panels.common.actions import (
    EducatorReasonMixin,
    _empty_message,
    _register_title,
    inactive_cohort_response,
)
from freedom_ls.educator_interface.panels.common.registration_actions import (
    ADD_COHORT_REGISTRATION,
    CohortRegistrationDeactivation,
)
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.educator_interface.panels.learner.actions import (
    AddLearnerAction,
    _membership_changed_response,
)
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.learner_actions import (
    add_to_cohort,
    deactivate_cohort,
    reactivate_cohort,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    Learner,
)
from freedom_ls.learner_management.queries import (
    ADD_COHORTMEMBERSHIP,
    ADD_LEARNER,
    cohort_course_count,
    cohort_is_empty,
    import_into_cohort_in_progress,
    learners_visible_to,
)
from freedom_ls.learner_management.utils import (
    record_cohort_entry,
    register_cohort_for_course,
)
from freedom_ls.role_based_permissions.utils import delete_role_rows_for

__all__ = [
    "AddExistingLearnersAction",
    "AddLearnerToCohortAction",
    "CohortStateAction",
    "DeactivateCohortAction",
    "DeactivateCohortRegistrationAction",
    "DeleteEmptyCohortAction",
    "EditCohortAction",
    "ReactivateCohortAction",
    "RegisterCohortForCourseAction",
    "RequiresActiveCohortMixin",
    "cohort_not_empty_sentence",
    "cohort_state_actions",
]


def cohort_not_empty_sentence(cohort: Cohort) -> str:
    """Why a cohort cannot be deleted: everything deletion would cascade
    away, deactivated learners and inactive registrations included, and an
    import into it that has not finished. Empty for a deletable cohort, so
    one call tells a caller both things."""
    learners = cohort.cohortmembership_set.count()
    registrations = cohort.course_registrations.count()
    parts = []
    if learners:
        parts.append(count_noun(Learner, learners))
    if registrations:
        parts.append(
            count_phrase(registrations, "course registration", "course registrations")
        )
    importing = import_into_cohort_in_progress(cohort)
    if not parts:
        if not importing:
            return ""
        return (
            f"{cohort} can't be deleted while a learner import into it is in progress."
        )
    sentence = (
        f"{cohort} can't be deleted while it has {join_prose(parts)}, counting "
        "inactive learners and inactive registrations."
    )
    if importing:
        sentence += " A learner import into it is also in progress."
    return sentence


class RequiresActiveCohortMixin(PanelAction):
    """Offers an action only while the cohort is active, and refuses a submit
    for an inactive one. Declared on PanelAction so the overrides type-check;
    list it before the action it guards in the bases. A subclass sets
    `blocked_phrase`, the refused action in the words of "Reactivate the
    cohort to ..."; it has no default, so a subclass that forgets fails when
    it first refuses."""

    blocked_phrase: str

    def is_offered(self, ctx: PanelContext) -> bool:
        return cast(Cohort, ctx.instance).is_active

    def refuse_inactive(self, ctx: PanelContext) -> HttpResponse:
        return inactive_cohort_response(
            ctx, cast(Cohort, ctx.instance), self.blocked_phrase
        )

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
    """The cohort's name, a field on the Settings tab's Name panel rather than a
    dialog, offered only while the cohort is active. The panel includes the
    form on first render; a 422 re-renders the form in place, and a save
    answers 204 so the panel's own cohortChanged refresh shows the new name.
    """

    blocked_phrase = "change its name"
    renders_in_footer = False
    template_name = "educator_interface/partials/cohort_name_form.html"
    autofocus_first_field = False

    def refuse_inactive(self, ctx: PanelContext) -> HttpResponse:
        # The form targets itself, so the inactive-cohort notice is
        # retargeted at the dialog, where every other refusal shows.
        response = super().refuse_inactive(ctx)
        response["HX-Retarget"] = "#app-modal-body"
        response["HX-Reswap"] = "innerHTML"
        return response

    def form_valid(self, ctx: PanelContext, form: forms.BaseForm) -> HttpResponse:
        old_name = str(form.initial["name"])
        with transaction.atomic():
            response = super().form_valid(ctx, form)
            if "name" in form.changed_data:
                cohort = cast(Cohort, cast(forms.ModelForm, form).instance)
                record_cohort_entry(
                    cohort,
                    "cohort.renamed",
                    cast("User", ctx.request.user),
                    details={"old": old_name, "new": cohort.name},
                )
        return response


class CohortStateAction(ConfirmAction):
    """Moves a cohort to `target_state`, after confirmation."""

    capability = "freedom_ls_learner_management.change_cohort"
    target_state: bool

    def perform(self, cohort: Cohort, *, actor: User, reason: str) -> bool:
        raise NotImplementedError

    def get_confirm_context(self, ctx: PanelContext) -> dict[str, object]:
        cohort = cast(Cohort, ctx.instance)
        not_empty_sentence = cohort_not_empty_sentence(cohort)
        return {
            "cohort": cohort,
            "cohort_course_count": cohort_course_count(cohort),
            "not_empty_sentence": not_empty_sentence,
            "is_empty": not not_empty_sentence,
        }

    def refuse_unchanged(self, ctx: PanelContext, cohort: Cohort) -> HttpResponse:
        """The 422 for a cohort already in `target_state`."""
        raise NotImplementedError

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        cohort = cast(Cohort, ctx.instance)
        if not self.perform(
            cohort, actor=cast("User", ctx.request.user), reason=ctx.reason
        ):
            return self.refuse_unchanged(ctx, cohort)
        # The page re-renders in full, header included, so no domain event is
        # sent: the panels would only refetch themselves and then be replaced.
        return navigation_response(current_page_within(ctx.request, ctx.page_url))


class DeactivateCohortAction(
    EducatorReasonMixin, RequiresActiveCohortMixin, CohortStateAction
):
    label = "Deactivate"
    action_name = "deactivate"
    target_state = False
    loading_text = "Deactivating…"
    template_name = "educator_interface/modal/deactivate_confirmation.html"

    def perform(self, cohort: Cohort, *, actor: User, reason: str) -> bool:
        return deactivate_cohort(cohort, actor=actor, reason=reason)

    def refuse_unchanged(self, ctx: PanelContext, cohort: Cohort) -> HttpResponse:
        return self.refuse(
            ctx,
            "Nothing changed. Someone else may have deactivated it already.",
            title=f"{cohort} is already inactive",
        )

    def refuse_inactive(self, ctx: PanelContext) -> HttpResponse:
        return self.refuse_unchanged(ctx, cast(Cohort, ctx.instance))


class ReactivateCohortAction(CohortStateAction):
    label = "Reactivate"
    action_name = "reactivate"
    target_state = True
    loading_text = "Reactivating…"
    template_name = "educator_interface/modal/reactivate_confirmation.html"

    def perform(self, cohort: Cohort, *, actor: User, reason: str) -> bool:
        return reactivate_cohort(cohort, actor=actor, reason=reason)

    def is_offered(self, ctx: PanelContext) -> bool:
        return not cast(Cohort, ctx.instance).is_active

    def refuse_unchanged(self, ctx: PanelContext, cohort: Cohort) -> HttpResponse:
        return self.refuse(
            ctx,
            "Nothing changed. Someone else may have reactivated it already.",
            title=f"{cohort} is already active",
        )


class DeleteEmptyCohortAction(EducatorReasonMixin, DeleteAction):
    """Deletes a cohort that has no memberships and no course registrations.

    A cohort that is not empty is neither offered the action nor allowed to
    submit it: deletion would cascade away deactivated learners' memberships and
    inactive registrations, which nobody sees on the page.
    """

    def is_offered(self, ctx: PanelContext) -> bool:
        cohort = cast(Cohort, ctx.instance)
        return cohort_is_empty(cohort) and not import_into_cohort_in_progress(cohort)

    def get_title(self, ctx: PanelContext) -> str:
        return f"{super().get_title(ctx)}?"

    def get_known_blocked_reason(self, ctx: PanelContext, instance: Model) -> str:
        return cohort_not_empty_sentence(cast(Cohort, instance))

    def before_delete(self, ctx: PanelContext, instance: Model) -> HttpResponse | None:
        # Lock the cohort so a membership added between this check and the
        # delete either lands first and is refused here, or waits and then
        # fails on the missing cohort. A cohort another request deleted
        # while this one waited is a 404, which the action route answers
        # with its "unavailable" fragment. The action route authorised
        # ctx.instance before this ran; the re-read only takes the lock.
        cohort = get_object_or_404(Cohort.objects.select_for_update(), pk=instance.pk)
        not_empty = cohort_not_empty_sentence(cohort)
        if not_empty:
            return self._blocked_response(ctx, cohort, not_empty)
        actor = cast("User", ctx.request.user)
        reason = ctx.reason
        # The roles go here rather than in the pre_delete receiver, which
        # has no request and would log their removal as the system.
        delete_role_rows_for(cohort, removed_by=actor, reason=reason)
        # Written before the delete because the entry reads the pk, which
        # delete() clears. A delete that a protected relation then blocks
        # rolls the entry back with it.
        record_cohort_entry(cohort, "cohort.deleted", actor, reason=reason)
        return None


class RegisterCohortForCourseAction(RequiresActiveCohortMixin, FormPanelAction):
    """Registers the cohort for a course it holds no active registration for."""

    label = "Register for a course"
    action_name = "register"
    blocked_phrase = "register it for a course"
    capability = ADD_COHORT_REGISTRATION
    form_class = CohortCourseRegistrationForm
    refresh_on_change = ("course",)
    submit_buttons = [
        {"label": "Register", "variant": "primary", "loading_text": "Registering…"}
    ]

    def get_form_kwargs(self, ctx: PanelContext) -> dict[str, object]:
        return {**super().get_form_kwargs(ctx), "cohort": ctx.instance}

    def get_form_title(self, ctx: PanelContext, form: forms.BaseForm) -> str:
        return _register_title(
            form, str(ctx.instance), cast(Cohort, ctx.instance).organisation
        )

    def form_valid(self, ctx: PanelContext, form: forms.BaseForm) -> HttpResponse:
        register_cohort_for_course(
            cast(Cohort, ctx.instance),
            form.cleaned_data["course"],
            actor=cast("User", ctx.request.user),
        )
        # The courses tab, its count and the header's course stat all
        # re-render, which a panel refresh alone could not do for the header.
        return navigation_response(ctx.page_url)


class DeactivateCohortRegistrationAction(
    EducatorReasonMixin, RequiresActiveCohortMixin, CohortRegistrationDeactivation
):
    """Deactivates one of the cohort's active course registrations from its
    Courses tab, where the action renders per row, never as a footer button."""

    blocked_phrase = "deactivate one of its course registrations"

    def registration_scope(
        self, ctx: PanelContext
    ) -> QuerySet[CohortCourseRegistration]:
        return cast(Cohort, ctx.instance).course_registrations.all()

    def success_response(
        self, ctx: PanelContext, registration: CohortCourseRegistration
    ) -> HttpResponse:
        # The courses tab, its count and the header's course stat all
        # re-render, which a panel refresh alone could not do for the header.
        return navigation_response(ctx.page_url)


class AddExistingLearnersAction(RequiresActiveCohortMixin, FormPanelAction):
    """Adds existing learners to the cohort on the page, for a user who may
    add cohort members but not create learners."""

    label = "Add learners"
    action_name = "add_existing_learners"
    blocked_phrase = "add learners to it"
    variant = "secondary"
    capability = ADD_COHORTMEMBERSHIP
    form_class = LearnerPickerForm
    submit_buttons = [
        {"label": "Add learners", "variant": "primary", "loading_text": "Adding…"}
    ]

    def is_offered(self, ctx: PanelContext) -> bool:
        scoped = cast("OrganisationScopedRequest", ctx.request)
        return super().is_offered(ctx) and not can(
            scoped.user, ADD_LEARNER, scoped.organisation
        )

    def get_form_kwargs(self, ctx: PanelContext) -> dict[str, object]:
        scoped = cast("OrganisationScopedRequest", ctx.request)
        cohort = cast(Cohort, ctx.instance)
        return {
            **super().get_form_kwargs(ctx),
            "queryset": learners_visible_to(scoped.user, scoped.organisation)
            .select_related("user")
            .exclude(cohortmembership__cohort=cohort),
        }

    def get_form_title(self, ctx: PanelContext, form: forms.BaseForm) -> str:
        return f"Add learners to {cast(Cohort, ctx.instance)}"

    def get_empty_message(self, ctx: PanelContext, form: forms.BaseForm) -> str | None:
        return _empty_message(
            form,
            "learners",
            f"Everyone in your other cohorts is already in {ctx.instance}. "
            "To add someone new, ask an organisation admin.",
        )

    def form_valid(self, ctx: PanelContext, form: forms.BaseForm) -> HttpResponse:
        cohort = cast(Cohort, ctx.instance)
        learners = form.cleaned_data["learners"]
        with transaction.atomic():
            for learner in learners:
                add_to_cohort(learner, cohort, actor=cast("User", ctx.request.user))
        return _membership_changed_response(
            [str(learner.pk) for learner in learners], [str(cohort.pk)]
        )


class AddLearnerToCohortAction(RequiresActiveCohortMixin, AddLearnerAction):
    """Add a learner on a cohort's page, with the cohort preset. Offered only
    to a user who may create learners; others get the existing-learner picker."""

    blocked_phrase = "add learners to it"

    def is_offered(self, ctx: PanelContext) -> bool:
        scoped = cast("OrganisationScopedRequest", ctx.request)
        return super().is_offered(ctx) and can(
            scoped.user, ADD_LEARNER, scoped.organisation
        )


def cohort_state_actions() -> list[PanelAction]:
    """Both state actions; `is_offered` picks which one renders."""
    return [DeactivateCohortAction(), ReactivateCohortAction()]
