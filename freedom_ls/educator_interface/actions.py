"""Panel actions on a cohort that need more than the generic framework ones."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from django import forms
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.db import transaction
from django.db.models import Model, QuerySet, prefetch_related_objects
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseNotAllowed,
    QueryDict,
)
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import urlencode

from freedom_ls.accounts.account_setup import (
    AccountAlreadySetUp,
    SetupEmailRecentlySent,
    is_pending,
    pending_user_q,
    resend_account_setup_email,
)
from freedom_ls.accounts.config import config as accounts_config
from freedom_ls.accounts.models import User, display_name_for
from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.events import (
    COHORT_CHANGED,
    LEARNER_CHANGED,
    REGISTRATION_CHANGED,
)
from freedom_ls.educator_interface.forms import (
    AddLearnerForm,
    BulkTargetPickerForm,
    CohortCourseRegistrationForm,
    CohortPickerForm,
    LearnerCourseRegistrationForm,
    LearnerNameForm,
    LearnerPickerForm,
    choice_error,
)
from freedom_ls.educator_interface.learner_import import check_import_gate
from freedom_ls.educator_interface.panels.common.actions import (
    EducatorReasonMixin,
    _action_params,
    _empty_message,
    _picker_title,
    _register_title,
    _uuid_from,
)
from freedom_ls.educator_interface.panels.common.bulk_actions import (
    CoursePickerMixin,
    EducatorBulkAction,
)
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.learner_actions import (
    AddLearnerResult,
    AddOutcome,
    CohortUnavailableError,
    add_learner,
    add_to_cohort,
    deactivate_cohort,
    deactivate_learner,
    deactivate_registration,
    move_between_cohorts,
    reactivate_cohort,
    reactivate_learner,
    record_learner_entry,
    register_for_course,
    remove_from_cohort,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.queries import (
    ADD_COHORTCOURSEREGISTRATION,
    ADD_COHORTMEMBERSHIP,
    ADD_LEARNER,
    ADD_LEARNERCOURSEREGISTRATION,
    CHANGE_COHORT,
    CHANGE_COHORTCOURSEREGISTRATION,
    CHANGE_LEARNER,
    CHANGE_LEARNERCOURSEREGISTRATION,
    COURSE_NOT_OPEN_MESSAGE,
    DELETE_COHORTMEMBERSHIP,
    CourseNotOpenError,
    cohort_course_count,
    cohort_is_empty,
    cohort_learner_count,
    cohorts_visible_to,
    courses_gaining_access,
    courses_losing_access,
    courses_lost_by_any,
    import_into_cohort_in_progress,
    is_course_available_to_organisation,
    learners_keeping_access_count,
    learners_permitted_for,
    learners_visible_to,
    members_keeping_access,
    other_grants_for,
)
from freedom_ls.learner_management.utils import (
    deactivate_cohort_registration,
    record_cohort_entry,
    register_cohort_for_course,
)
from freedom_ls.learner_progress.utils import move_progress_preview
from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.panel_framework.actions import (
    ConfirmAction,
    DeleteAction,
    EditAction,
    FormPanelAction,
    ModalPanelAction,
    PanelAction,
    changed_response,
    count_noun,
    count_phrase,
    current_page_within,
    denied_response,
    join_prose,
    navigation_response,
    refusal_response,
)
from freedom_ls.panel_framework.bulk_actions import (
    BulkCount,
    BulkOutcome,
    register_bulk_action,
)
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.events import build_hx_trigger
from freedom_ls.role_based_permissions.utils import delete_role_rows_for


def inactive_cohort_response(
    ctx: PanelContext, cohort: Cohort, blocked_phrase: str
) -> HttpResponse:
    """The 422 fragment for a change aimed at an inactive cohort.
    `blocked_phrase` completes "Reactivate the cohort ... to" with what the
    refused action would have done, such as "deactivate it"."""
    return refusal_response(
        ctx,
        title=f"{cohort} is inactive",
        message=(
            "The change was not made. Reactivate the cohort from its Settings "
            f"tab to {blocked_phrase}."
        ),
    )


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


class EditLearnerNameAction(EditAction):
    """Edit the learner's first and last name, which live on their user, as
    fields on the Settings tab's Name panel rather than a dialog. A 422
    re-renders the form in place; a save answers 204 so the panel's own
    learnerChanged refresh shows the new name."""

    label = "Edit name"
    action_name = "edit_name"
    renders_in_footer = False
    template_name = "educator_interface/partials/learner_name_form.html"
    autofocus_first_field = False

    def __init__(self, learner: Learner) -> None:
        super().__init__(
            form_class=LearnerNameForm,
            form_title=f"Edit {learner.user.display_name}",
            instance=learner.user,
            success_events=(LEARNER_CHANGED,),
        )
        self._learner = learner

    def get_form_kwargs(self, ctx: PanelContext) -> dict[str, object]:
        # The page's instance is the learner; the form edits their user.
        return {**super().get_form_kwargs(ctx), "instance": self._instance}

    def event_instance(self, form: forms.ModelForm) -> Model:
        return self._learner

    def form_valid(self, ctx: PanelContext, form: forms.BaseForm) -> HttpResponse:
        # The form has already bound the new names onto the user; its initial
        # data still holds the stored ones.
        user = cast("User", cast(forms.ModelForm, form).instance)
        old_name = display_name_for(
            form.initial["first_name"], form.initial["last_name"], user.email
        )
        with transaction.atomic():
            response = super().form_valid(ctx, form)
            if {"first_name", "last_name"} & set(form.changed_data):
                record_learner_entry(
                    self._learner,
                    "learner.renamed",
                    cast("User", ctx.request.user),
                    details={"old": old_name, "new": user.display_name},
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
    capability = "freedom_ls_learner_management.add_cohortcourseregistration"
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


class LearnerStateAction(ConfirmAction):
    """Moves a learner to `target_state`, after confirmation."""

    capability = "freedom_ls_learner_management.change_learner"
    target_state: bool

    def perform(self, learner: Learner, actor: User, reason: str = "") -> bool:
        raise NotImplementedError

    def is_offered(self, ctx: PanelContext) -> bool:
        return cast(Learner, ctx.instance).is_active != self.target_state

    def get_confirm_context(self, ctx: PanelContext) -> dict[str, object]:
        learner = cast(Learner, ctx.instance)
        return {
            "learner": learner,
            "on_default_organisation": (
                learner.organisation_id == get_default_organisation(learner.site).pk
            ),
        }

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        learner = cast(Learner, ctx.instance)
        if not self.perform(learner, cast("User", ctx.request.user), ctx.reason):
            return self.refuse(
                ctx,
                (
                    "Nothing changed. Someone else may have already used "
                    f"{self.label} on this learner."
                ),
                title=f"{learner.user.display_name} was already changed",
            )
        # The header's badge and actions change, so the page re-renders in
        # full, on the tab it was on, and no domain event is sent.
        return navigation_response(current_page_within(ctx.request, ctx.page_url))


class DeactivateLearnerAction(EducatorReasonMixin, LearnerStateAction):
    label = "Deactivate"
    action_name = "deactivate"
    target_state = False
    loading_text = "Deactivating…"
    template_name = "educator_interface/modal/deactivate_learner_confirmation.html"

    def perform(self, learner: Learner, actor: User, reason: str = "") -> bool:
        return deactivate_learner(learner, actor=actor, reason=reason)


class ReactivateLearnerAction(LearnerStateAction):
    label = "Reactivate"
    action_name = "reactivate"
    target_state = True
    loading_text = "Reactivating…"
    template_name = "educator_interface/modal/reactivate_learner_confirmation.html"

    def perform(self, learner: Learner, actor: User, reason: str = "") -> bool:
        return reactivate_learner(learner, actor=actor)


def learner_state_actions() -> list[PanelAction]:
    """Both state actions; `is_offered` picks which one renders."""
    return [DeactivateLearnerAction(), ReactivateLearnerAction()]


def record_and_resend_setup_email(learner: Learner, actor: User) -> None:
    """Send the learner the account setup email again and record who asked
    for it. Raises what `resend_account_setup_email` raises."""
    with transaction.atomic():
        # The entry goes first: a refused send rolls it back, while a failed
        # entry must not leave an email sent and the resend guard set with
        # nothing in the log.
        record_learner_entry(learner, "learner.setup_email_resent", actor)
        resend_account_setup_email(learner.user, learner.organisation.name)


class ResendSetupEmailAction(ConfirmAction):
    """Sends a pending learner the account setup email again, after confirmation."""

    label = "Resend setup email"
    action_name = "resend_setup_email"
    loading_text = "Sending…"
    capability = "freedom_ls_learner_management.change_learner"
    template_name = "educator_interface/modal/resend_setup_email_confirmation.html"

    def is_offered(self, ctx: PanelContext) -> bool:
        return is_pending(cast(Learner, ctx.instance).user)

    def get_confirm_context(self, ctx: PanelContext) -> dict[str, object]:
        return {"learner": ctx.instance}

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        learner = cast(Learner, ctx.instance)
        try:
            record_and_resend_setup_email(learner, cast("User", ctx.request.user))
        except SetupEmailRecentlySent:
            minutes = accounts_config.SETUP_EMAIL_RESEND_SECONDS // 60
            return self.refuse(
                ctx,
                (
                    f"{learner.user.display_name} was sent a setup email recently. "
                    f"Try again in {minutes} minutes."
                ),
                title="Setup email sent recently",
            )
        except AccountAlreadySetUp:
            name = learner.user.display_name
            return self.refuse(
                ctx,
                (
                    f"Nothing was sent. {name} has signed in or set a password "
                    "since this page loaded."
                ),
                title=f"{name} has already set up their account",
            )
        return changed_response({LEARNER_CHANGED: [str(learner.pk)]})


KEEPING_NAMES_SHOWN = 10


class DeactivateCohortRegistrationAction(
    EducatorReasonMixin, RequiresActiveCohortMixin, ConfirmAction
):
    """Deactivates one of the cohort's active course registrations, after
    confirmation. The registration travels as a `registration` parameter, so
    the action resolves on the courses tab and renders per row there, never
    as a footer button."""

    label = "Deactivate"
    action_name = "deactivate_cohort_registration"
    blocked_phrase = "deactivate one of its course registrations"
    renders_in_footer = False
    capability = "freedom_ls_learner_management.change_cohortcourseregistration"
    loading_text = "Deactivating…"
    template_name = (
        "educator_interface/modal/deactivate_cohort_registration_confirmation.html"
    )

    row_param = "registration"

    def get_row_queryset(self, ctx: PanelContext) -> QuerySet[CohortCourseRegistration]:
        return (
            cast(Cohort, ctx.instance)
            .course_registrations.select_related("course")
            .filter(is_active=True)
        )

    def _registration(self, ctx: PanelContext) -> CohortCourseRegistration:
        return cast(CohortCourseRegistration, self.get_row_object(ctx))

    def get_confirm_context(self, ctx: PanelContext) -> dict[str, object]:
        cohort = cast(Cohort, ctx.instance)
        registration = self._registration(ctx)
        keeping = list(members_keeping_access(registration))
        member_count = cohort_learner_count(cohort)
        names = [learner.user.display_name for learner in keeping[:KEEPING_NAMES_SHOWN]]
        if len(keeping) > KEEPING_NAMES_SHOWN:
            names.append(f"{len(keeping) - KEEPING_NAMES_SHOWN} more")
        return {
            "cohort": cohort,
            "registration": registration,
            "course": registration.course,
            "losing_count": member_count - len(keeping),
            "losing_phrase": count_noun(Learner, member_count - len(keeping)),
            "keeping_names": join_prose(names),
        }

    def handle_active_submit(self, ctx: PanelContext) -> HttpResponse:
        deactivate_cohort_registration(
            self._registration(ctx),
            actor=cast("User", ctx.request.user),
            reason=ctx.reason,
        )
        # The courses tab, its count and the header's course stat all
        # re-render, which a panel refresh alone could not do for the header.
        return navigation_response(ctx.page_url)


def _registration_changed_response(learner: Learner) -> HttpResponse:
    ids = [str(learner.pk)]
    return changed_response({REGISTRATION_CHANGED: ids, LEARNER_CHANGED: ids})


class RegisterLearnerForCourseAction(FormPanelAction):
    """Registers the learner on the page for a course they hold no active
    individual registration for."""

    label = "Register for a course"
    action_name = "register_for_course"
    capability = "freedom_ls_learner_management.add_learnercourseregistration"
    form_class = LearnerCourseRegistrationForm
    refresh_on_change = ("course",)
    submit_buttons = [
        {"label": "Register", "variant": "primary", "loading_text": "Registering…"}
    ]

    def get_form_kwargs(self, ctx: PanelContext) -> dict[str, object]:
        return {**super().get_form_kwargs(ctx), "learner": ctx.instance}

    def get_form_title(self, ctx: PanelContext, form: forms.BaseForm) -> str:
        learner = cast(Learner, ctx.instance)
        return _register_title(form, learner.user.display_name, learner.organisation)

    def get_empty_message(self, ctx: PanelContext, form: forms.BaseForm) -> str | None:
        name = cast(Learner, ctx.instance).user.display_name
        return _empty_message(
            form,
            "course",
            f"There is no course {name} can be registered for right now.",
        )

    def form_valid(self, ctx: PanelContext, form: forms.BaseForm) -> HttpResponse:
        learner = cast(Learner, ctx.instance)
        register_for_course(
            learner,
            form.cleaned_data["course"],
            actor=cast("User", ctx.request.user),
        )
        return _registration_changed_response(learner)


class DeactivateRegistrationAction(EducatorReasonMixin, ConfirmAction):
    """Deactivates one of the learner's active individual registrations, after
    confirmation. The registration travels as a `registration` parameter, so
    the action resolves on the registrations card and renders per row there,
    never as a footer button."""

    label = "Deactivate"
    action_name = "deactivate_registration"
    renders_in_footer = False
    capability = "freedom_ls_learner_management.change_learnercourseregistration"
    loading_text = "Deactivating…"
    template_name = "educator_interface/modal/deactivate_registration_confirmation.html"

    row_param = "registration"

    def get_row_queryset(
        self, ctx: PanelContext
    ) -> QuerySet[LearnerCourseRegistration]:
        return LearnerCourseRegistration.objects.filter(
            learner=cast(Learner, ctx.instance), is_active=True
        ).select_related("course")

    def _registration(self, ctx: PanelContext) -> LearnerCourseRegistration:
        return cast(LearnerCourseRegistration, self.get_row_object(ctx))

    def get_confirm_context(self, ctx: PanelContext) -> dict[str, object]:
        learner = cast(Learner, ctx.instance)
        registration = self._registration(ctx)
        scoped = cast("OrganisationScopedRequest", ctx.request)
        granting = other_grants_for(learner, registration.course)
        # A cohort the educator cannot see is never named.
        visible_ids = set(
            cohorts_visible_to(scoped.user, scoped.organisation).values_list(
                "pk", flat=True
            )
        )
        return {
            "learner": learner,
            "registration": registration,
            "course": registration.course,
            "keeping_cohorts": join_prose(
                [cohort.name for cohort in granting if cohort.pk in visible_ids]
            ),
            "keeps_access": bool(granting),
            "on_default_organisation": (
                learner.organisation_id == get_default_organisation(learner.site).pk
            ),
        }

    def handle_confirmed_submit(self, ctx: PanelContext) -> HttpResponse:
        learner = cast(Learner, ctx.instance)
        deactivate_registration(
            learner,
            self._registration(ctx).course,
            actor=cast("User", ctx.request.user),
            reason=ctx.reason,
        )
        return _registration_changed_response(learner)


class ReactivateRegistrationAction(ConfirmAction):
    """Reactivates one of the learner's inactive individual registrations,
    after confirmation. Like deactivating, the registration travels as a
    `registration` parameter and the action renders per row."""

    label = "Reactivate"
    action_name = "reactivate_registration"
    renders_in_footer = False
    capability = "freedom_ls_learner_management.change_learnercourseregistration"
    loading_text = "Reactivating…"
    template_name = "educator_interface/modal/reactivate_registration_confirmation.html"

    row_param = "registration"

    def get_row_queryset(
        self, ctx: PanelContext
    ) -> QuerySet[LearnerCourseRegistration]:
        return LearnerCourseRegistration.objects.filter(
            learner=cast(Learner, ctx.instance), is_active=False
        ).select_related("course")

    def _registration(self, ctx: PanelContext) -> LearnerCourseRegistration:
        return cast(LearnerCourseRegistration, self.get_row_object(ctx))

    def get_confirm_context(self, ctx: PanelContext) -> dict[str, object]:
        registration = self._registration(ctx)
        return {
            "learner": cast(Learner, ctx.instance),
            "registration": registration,
            "course": registration.course,
        }

    def _refused(self, ctx: PanelContext, message: str) -> HttpResponse:
        context = self.get_context_data(ctx)
        context["refusal"] = message
        return render(ctx.request, self.template_name, context, status=422)

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        learner = cast(Learner, ctx.instance)
        course = self._registration(ctx).course
        # The write gate accepts every public course, but an educator registers
        # only for courses available to the organisation.
        if not is_course_available_to_organisation(course, learner.organisation):
            return self._refused(ctx, COURSE_NOT_OPEN_MESSAGE)
        try:
            register_for_course(learner, course, actor=cast("User", ctx.request.user))
        except CourseNotOpenError as error:
            # The course may have gained organisations since the registration
            # was made, leaving it closed to this learner's organisation.
            return self._refused(ctx, str(error))
        return _registration_changed_response(learner)


def _membership_changed_response(
    learner_event_ids: list[str], cohort_event_ids: list[str]
) -> HttpResponse:
    """The 204 every membership change answers with: both events, and the
    modal closed."""
    return changed_response(
        {LEARNER_CHANGED: learner_event_ids, COHORT_CHANGED: cohort_event_ids}
    )


def _joinable_cohorts(ctx: PanelContext, learner: Learner) -> QuerySet[Cohort]:
    """Active cohorts the user may add `learner` to and they are not in."""
    scoped = cast("OrganisationScopedRequest", ctx.request)
    return (
        cohorts_visible_to(
            scoped.user, scoped.organisation, capability=ADD_COHORTMEMBERSHIP
        )
        .filter(is_active=True)
        .exclude(cohortmembership__learner=learner)
    )


def _picker_cohorts(ctx: PanelContext, learner: Learner) -> QuerySet[Cohort]:
    """The cohorts a picker for `learner` draws on.

    A POST picks from every cohort of the organisation the learner is not in,
    wider than the offered set, so a cohort the user may see but not add to
    reaches the permission check and is refused as a denial.
    """
    if ctx.request.method == "POST":
        scoped = cast("OrganisationScopedRequest", ctx.request)
        return Cohort.objects.filter(organisation=scoped.organisation).exclude(
            cohortmembership__learner=learner
        )
    return _joinable_cohorts(ctx, learner)


def _cohort_picker(
    ctx: PanelContext,
    learner: Learner,
    get_data: Mapping[str, str] | None,
    *,
    field_name: str = "cohort",
) -> CohortPickerForm:
    """The picker of cohorts to put `learner` in, bound to `get_data` on a GET."""
    data = ctx.request.POST if ctx.request.method == "POST" else get_data
    return CohortPickerForm(
        data, queryset=_picker_cohorts(ctx, learner), field_name=field_name
    )


class MembershipAction(ModalPanelAction):
    """A change to one learner's membership of one cohort, after confirmation.

    The action resolves on the learner page, where the cohort travels as a
    `cohort` parameter, and on the cohort page, where the learner travels as
    a `learner` parameter. It renders per row, never as a footer button.
    A subclass sets `blocked_phrase`, what an inactive cohort refuses.
    """

    blocked_phrase: str
    variant = "secondary"
    renders_in_footer = False
    row_param = "cohort"

    def get_row_queryset(self, ctx: PanelContext) -> QuerySet[Cohort]:
        scoped = cast("OrganisationScopedRequest", ctx.request)
        return cohorts_visible_to(scoped.user, scoped.organisation)

    def perform(
        self, learner: Learner, cohort: Cohort, actor: User, reason: str = ""
    ) -> bool:
        raise NotImplementedError

    def _cohort(self, ctx: PanelContext) -> Cohort:
        if isinstance(ctx.instance, Cohort):
            return ctx.instance
        return cast(Cohort, self.get_row_object(ctx))

    def _pair(self, ctx: PanelContext) -> tuple[Learner, Cohort]:
        if isinstance(ctx.instance, Cohort):
            scoped = cast("OrganisationScopedRequest", ctx.request)
            learner_pk = _uuid_from(_action_params(ctx.request), "learner")
            learner = ctx.once(
                (MembershipAction, "learner", learner_pk),
                lambda: get_object_or_404(
                    learners_visible_to(
                        scoped.user, scoped.organisation, include_inactive=True
                    ),
                    pk=learner_pk,
                ),
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
            return inactive_cohort_response(ctx, cohort, self.blocked_phrase)
        self.perform(learner, cohort, cast("User", ctx.request.user), ctx.reason)
        ids = [str(learner.pk), str(cohort.pk)]
        return _membership_changed_response(ids, ids)


class RemoveFromCohortAction(EducatorReasonMixin, ConfirmAction, MembershipAction):
    label = "Remove from cohort"
    action_name = "remove_from_cohort"
    blocked_phrase = "remove learners from it"
    capability = "freedom_ls_learner_management.delete_cohortmembership"
    confirm_label = "Remove"
    confirm_variant = "error"
    loading_text = "Removing…"
    template_name = "educator_interface/modal/remove_from_cohort_confirmation.html"

    def perform(
        self, learner: Learner, cohort: Cohort, actor: User, reason: str = ""
    ) -> bool:
        return remove_from_cohort(learner, cohort, actor=actor, reason=reason)

    def get_hidden_fields(self, ctx: PanelContext) -> dict[str, str]:
        """The other side of the pair, which the page does not name."""
        learner, cohort = self._pair(ctx)
        if isinstance(ctx.instance, Cohort):
            return {"learner": str(learner.pk)}
        return {"cohort": str(cohort.pk)}

    def get_confirm_context(self, ctx: PanelContext) -> dict[str, object]:
        learner, cohort = self._pair(ctx)
        return {
            "learner": learner,
            "cohort": cohort,
            "losing_courses": join_prose(
                [str(course) for course in courses_losing_access(learner, cohort)]
            ),
        }


class MoveToCohortAction(MembershipAction):
    """Moves a learner from the cohort on the row to an active cohort the user
    may add to. Choosing a destination re-renders the fragment with what the
    move changes."""

    label = "Move to another cohort"
    action_name = "move"
    capability = "freedom_ls_learner_management.delete_cohortmembership"
    template_name = "educator_interface/modal/move_confirmation.html"

    def _picker(self, ctx: PanelContext, learner: Learner) -> CohortPickerForm:
        get_data = ctx.request.GET if "destination" in ctx.request.GET else None
        return _cohort_picker(ctx, learner, get_data, field_name="destination")

    def _not_a_member_response(
        self, ctx: PanelContext, learner: Learner, source: Cohort
    ) -> HttpResponse:
        name = learner.user.display_name
        return refusal_response(
            ctx,
            title=f"{name} is no longer in {source}",
            message=f"Nothing changed. {name} is no longer a member of {source}, "
            "so they cannot be moved from it.",
        )

    def _is_member(self, learner: Learner, source: Cohort) -> bool:
        return CohortMembership.objects.filter(learner=learner, cohort=source).exists()

    def render_fragment(self, ctx: PanelContext) -> HttpResponse:
        learner, source = self._pair(ctx)
        if not self._is_member(learner, source):
            return self._not_a_member_response(ctx, learner, source)
        return super().render_fragment(ctx)

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        learner, source = self._pair(ctx)
        context = super().get_context_data(ctx)
        if not _joinable_cohorts(ctx, learner).exists():
            name = learner.user.display_name
            context.update(
                {
                    "form_title": f"Move {name} from {source}",
                    "empty_message": "There is no other active cohort you can "
                    f"move {name} to.",
                }
            )
            return context
        form = self._picker(ctx, learner)
        if isinstance(ctx.instance, Cohort):
            other_side = {"name": "learner", "value": str(learner.pk)}
        else:
            other_side = {"name": "cohort", "value": str(source.pk)}
        context.update(
            {
                "learner": learner,
                "cohort": source,
                "form": form,
                "other_side": other_side,
                "action_url": self.get_action_url(ctx),
            }
        )
        if form.is_bound and form.is_valid():
            destination = cast(Cohort, form.cleaned_data["destination"])
            context.update(
                {
                    "destination": destination,
                    "losing_courses": join_prose(
                        [
                            str(course)
                            for course in courses_losing_access(
                                learner, source, destination
                            )
                        ]
                    ),
                    "gaining_courses": join_prose(
                        [
                            str(course)
                            for course in courses_gaining_access(learner, destination)
                        ]
                    ),
                    "progress_outcomes": move_progress_preview(
                        learner, source, destination
                    ),
                }
            )
        return context

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        learner, source = self._pair(ctx)
        if not self._is_member(learner, source):
            return self._not_a_member_response(ctx, learner, source)
        form = self._picker(ctx, learner)
        if not form.is_valid():
            return self._refusal(ctx, choice_error("cohort")["invalid_choice"])
        destination = cast(Cohort, form.cleaned_data["destination"])
        if not can(ctx.request.user, ADD_COHORTMEMBERSHIP, destination):
            return denied_response(ctx, self)
        for cohort in (source, destination):
            if not cohort.is_active:
                return inactive_cohort_response(
                    ctx, cohort, "move learners into or out of it"
                )
        try:
            move_between_cohorts(
                learner, source, destination, actor=cast("User", ctx.request.user)
            )
        except ValueError as error:
            return self._refusal(ctx, str(error))
        ids = [str(learner.pk), str(source.pk), str(destination.pk)]
        return _membership_changed_response(ids, ids)

    def _refusal(self, ctx: PanelContext, reason: str) -> HttpResponse:
        learner, source = self._pair(ctx)
        if not self._is_member(learner, source):
            return self._not_a_member_response(ctx, learner, source)
        context = self.get_context_data(ctx)
        if context.get("empty_message"):
            return render(ctx.request, self.template_name, context, status=422)
        context["refusal"] = reason
        # The re-rendered select offers what the fresh dialog offered.
        form = cast(CohortPickerForm, context["form"])
        cast(
            forms.ModelChoiceField, form.fields["destination"]
        ).queryset = _joinable_cohorts(ctx, learner)
        return render(ctx.request, self.template_name, context, status=422)


class AddToCohortAction(FormPanelAction):
    """Adds the learner on the page to an active cohort the user may add to."""

    label = "Add to cohort"
    action_name = "add_to_cohort"
    variant = "secondary"
    capability = ADD_COHORTMEMBERSHIP
    form_class = CohortPickerForm
    refresh_on_change = ("cohort",)
    submit_buttons = [
        {"label": "Add to cohort", "variant": "primary", "loading_text": "Adding…"}
    ]

    def get_form_kwargs(self, ctx: PanelContext) -> dict[str, object]:
        return {
            **super().get_form_kwargs(ctx),
            "queryset": _picker_cohorts(ctx, cast(Learner, ctx.instance)),
        }

    def get_form_title(self, ctx: PanelContext, form: forms.BaseForm) -> str:
        name = cast(Learner, ctx.instance).user.display_name

        def chosen(cohort: Cohort) -> str:
            return f"Add {name} to {cohort.name}"

        return _picker_title(
            form, "cohort", unchosen=f"Add {name} to a cohort", chosen=chosen
        )

    def get_empty_message(self, ctx: PanelContext, form: forms.BaseForm) -> str | None:
        name = cast(Learner, ctx.instance).user.display_name
        return _empty_message(
            form,
            "cohort",
            f"{name} is already in every active cohort you can add learners to.",
        )

    def form_invalid(self, ctx: PanelContext, form: forms.BaseForm) -> HttpResponse:
        # A POST validates against a wider set so a refused cohort reaches the
        # permission check; the re-rendered select offers what the fresh dialog offered.
        cast(
            forms.ModelChoiceField, form.fields["cohort"]
        ).queryset = _joinable_cohorts(ctx, cast(Learner, ctx.instance))
        return super().form_invalid(ctx, form)

    def form_valid(self, ctx: PanelContext, form: forms.BaseForm) -> HttpResponse:
        cohort = cast(Cohort, form.cleaned_data["cohort"])
        if not can(ctx.request.user, ADD_COHORTMEMBERSHIP, cohort):
            return denied_response(ctx, self)
        if not cohort.is_active:
            return inactive_cohort_response(ctx, cohort, "add learners to it")
        learner = cast(Learner, ctx.instance)
        add_to_cohort(learner, cohort, actor=cast("User", ctx.request.user))
        return _membership_changed_response([str(learner.pk)], [str(cohort.pk)])


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


class AddLearnerAction(FormPanelAction):
    """Adds one email address as a learner of the organisation, making a
    pending account for an unknown address, and optionally puts them in a
    cohort. Add reports the outcome in the modal with Add another beside
    Close; Add and add another reports it above an empty form with the
    cohort kept, so a handful of people are added one at a time. A list of
    people is the file import."""

    label = "Add learner"
    action_name = "add_learner"
    capability = ADD_LEARNER
    form_class = AddLearnerForm
    submit_buttons = [
        {
            "label": "Add and add another",
            "variant": "secondary",
            "name": "action",
            "value": "add_another",
            "loading_text": "Adding…",
        },
        {"label": "Add", "variant": "primary", "loading_text": "Adding…"},
    ]
    _ADDED = (AddOutcome.CREATED, AddOutcome.JOINED, AddOutcome.REACTIVATED)

    def permission_object(self, ctx: PanelContext) -> Model | None:
        return cast("OrganisationScopedRequest", ctx.request).organisation

    def _cohorts(self, ctx: PanelContext) -> QuerySet[Cohort]:
        scoped = cast("OrganisationScopedRequest", ctx.request)
        return cohorts_visible_to(
            scoped.user, scoped.organisation, capability=ADD_COHORTMEMBERSHIP
        ).filter(is_active=True)

    def _preset_cohort(self, ctx: PanelContext) -> Cohort | None:
        """The cohort the dialog is fixed to: the page's own cohort, else one
        named in the query string. A form field of the same name never counts,
        so a submitted cohort is only ever validated against the offered set."""
        if isinstance(ctx.instance, Cohort):
            return ctx.instance
        if "cohort" not in ctx.request.GET:
            return None
        cohort_pk = _uuid_from(ctx.request.GET, "cohort")
        return ctx.once(
            (AddLearnerAction, "preset_cohort", cohort_pk),
            lambda: get_object_or_404(self._cohorts(ctx), pk=cohort_pk),
        )

    def get_form_kwargs(self, ctx: PanelContext) -> dict[str, object]:
        return {
            **super().get_form_kwargs(ctx),
            "cohorts": self._cohorts(ctx),
            "preset": self._preset_cohort(ctx),
        }

    def get_form_title(self, ctx: PanelContext, form: forms.BaseForm) -> str:
        preset = self._preset_cohort(ctx)
        return f"Add a learner to {preset}" if preset else "Add a learner"

    def _action_url(self, ctx: PanelContext, preset: Cohort | None) -> str:
        url = self.get_action_url(ctx)
        if preset is not None and not isinstance(ctx.instance, Cohort):
            return f"{url}?cohort={preset.pk}"
        return url

    def get_fragment_context(
        self, ctx: PanelContext, form: forms.BaseForm
    ) -> dict[str, object]:
        return {
            **super().get_fragment_context(ctx, form),
            "action_url": self._action_url(ctx, self._preset_cohort(ctx)),
        }

    @staticmethod
    def _outcome_sentence(result: AddLearnerResult) -> str:
        sentence = f"{result.email}: {result.outcome.label}."
        if result.cohort_outcome:
            sentence += f" {result.cohort_outcome.label}."
        return sentence

    def form_valid(self, ctx: PanelContext, form: forms.BaseForm) -> HttpResponse:
        preset = self._preset_cohort(ctx)
        add_form = cast(AddLearnerForm, form)
        cohort = cast(Cohort | None, form.cleaned_data["cohort"]) or preset
        organisation = cast("OrganisationScopedRequest", ctx.request).organisation
        try:
            result = add_learner(
                organisation,
                add_form.entry(),
                cohort,
                actor=cast("User", ctx.request.user),
            )
        except CohortUnavailableError:
            return inactive_cohort_response(
                ctx, cast(Cohort, cohort), "add learners to it"
            )
        if ctx.request.POST.get("action") == "add_another":
            html = render_to_string(
                self.get_fragment_template_name(),
                {
                    **self.get_fragment_context(ctx, self.get_unbound_form(ctx)),
                    "status_message": self._outcome_sentence(result),
                },
                request=ctx.request,
            )
        else:
            html = render_to_string(
                "educator_interface/modal/add_learner_result.html",
                {
                    "result": result,
                    "added": result.outcome in self._ADDED,
                    "cohort": cohort,
                    "action_url": self._action_url(ctx, preset),
                },
                request=ctx.request,
            )
        events: dict[str, list[str]] = {
            LEARNER_CHANGED: [str(result.learner.pk)] if result.learner else []
        }
        if cohort is not None:
            events[COHORT_CHANGED] = [str(cohort.pk)]
        response = HttpResponse(html)
        response["HX-Trigger"] = build_hx_trigger(events)
        return response


class ImportLearnersAction(PanelAction):
    """A link to the learner import page, shown to a user who may import
    learners. On a cohort's page the link carries the cohort, which is then the
    import's cohort."""

    label = "Import learners"
    action_name = "import_learners"
    variant = "secondary"
    trigger_template_name = "educator_interface/partials/import_learners_link.html"

    @staticmethod
    def _cohort(ctx: PanelContext) -> Cohort | None:
        return ctx.instance if isinstance(ctx.instance, Cohort) else None

    def has_permission(self, ctx: PanelContext) -> bool:
        scoped = cast("OrganisationScopedRequest", ctx.request)
        return check_import_gate(
            cast("User", scoped.user), scoped.organisation, self._cohort(ctx)
        )

    def get_trigger_context(self, ctx: PanelContext) -> dict[str, object]:
        scoped = cast("OrganisationScopedRequest", ctx.request)
        cohort = self._cohort(ctx)
        href = reverse(
            "educator_interface:learner_import",
            kwargs={"organisation_slug": scoped.organisation.slug},
        )
        if cohort is not None:
            href = f"{href}?{urlencode({'cohort': str(cohort.pk)})}"
        return {**super().get_trigger_context(ctx), "href": href}

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        """A link has nothing to submit."""
        return HttpResponseNotAllowed(["GET"])


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


class LearnerBulkAction(EducatorBulkAction):
    """A bulk action over the rows of the learners table."""

    table_key = "learners"
    noun_model = Learner

    def with_related(self, queryset: QuerySet) -> QuerySet:
        return queryset.select_related("user", "organisation")

    def row_label(self, obj: Model) -> str:
        return cast(Learner, obj).user.display_name

    def permitted(
        self,
        user: AbstractBaseUser | AnonymousUser,
        scope: Model | None,
        queryset: QuerySet,
        cleaned_data: dict[str, object],
    ) -> QuerySet:
        return queryset.filter(
            pk__in=learners_permitted_for(
                user, cast(Organisation, scope), self.capability
            ).values("pk")
        )


class CohortMembershipBulkAction(LearnerBulkAction):
    """Adds learners to, or removes them from, the one cohort the educator
    picks. `staff_member_ids` holds the selected learners already in that cohort,
    read once per classification so previewing costs a fixed number of queries
    however many learners are selected."""

    form_class = BulkTargetPickerForm
    # The services refuse an inactive cohort, or one from another
    # organisation, with a ValueError; a cohort deactivated between the
    # confirmation and the run fails each learner instead of aborting the run.
    failure_exceptions = (ValueError,)
    staff_member_ids: frozenset[object] = frozenset()

    def get_form(
        self, request: HttpRequest, data: QueryDict | None
    ) -> BulkTargetPickerForm:
        scoped = cast("OrganisationScopedRequest", request)
        cohorts = cohorts_visible_to(
            scoped.user, scoped.organisation, capability=self.capability
        ).filter(is_active=True)
        return BulkTargetPickerForm(
            data, field_name="cohort", queryset=cohorts, label="Cohort"
        )

    def permitted(
        self,
        user: AbstractBaseUser | AnonymousUser,
        scope: Model | None,
        queryset: QuerySet,
        cleaned_data: dict[str, object],
    ) -> QuerySet:
        cohort = cast(Cohort | None, cleaned_data.get("cohort"))
        return (
            queryset
            if cohort and can(user, self.capability, cohort)
            else queryset.none()
        )

    def classify_all(
        self,
        request: HttpRequest,
        queryset: QuerySet,
        cleaned_data: dict[str, object],
    ) -> dict[str, BulkOutcome] | None:
        self.staff_member_ids = frozenset(
            CohortMembership.objects.filter(
                cohort=cleaned_data["cohort"], learner__in=queryset
            ).values_list("learner_id", flat=True)
        )
        return super().classify_all(request, queryset, cleaned_data)

    def target_json(self, cleaned_data: dict[str, object]) -> dict[str, str]:
        return {"cohort": str(cast(Cohort, cleaned_data["cohort"]).pk)}

    def resolve_target(
        self, scope: Model | None, target: dict[str, str]
    ) -> dict[str, object]:
        # Scoped to the organisation, so a saved target can never reach
        # another one's cohort.
        return {
            "cohort": get_object_or_404(
                Cohort._base_manager.filter(organisation=cast(Organisation, scope)),
                pk=target["cohort"],
            )
        }


@register_bulk_action
class AddToCohortBulkAction(CohortMembershipBulkAction):
    label = "Add to cohort"
    action_name = "add_to_cohort"
    loading_text = "Adding…"
    capability = ADD_COHORTMEMBERSHIP
    unchanged_reason = "already in the cohort"

    def skip_reason(self, obj: Model, cleaned_data: dict[str, object]) -> str | None:
        return self.unchanged_reason if obj.pk in self.staff_member_ids else None

    def perform(self, obj: Model, cleaned_data: dict[str, object], actor: User) -> bool:
        return add_to_cohort(
            cast(Learner, obj), cast(Cohort, cleaned_data["cohort"]), actor=actor
        )

    def sentence(self, count: int, cleaned_data: dict[str, object]) -> str:
        cohort = cast(Cohort, cleaned_data["cohort"])
        return f"Add {count_noun(Learner, count)} to {cohort.name}."


@register_bulk_action
class RemoveFromCohortBulkAction(CohortMembershipBulkAction):
    label = "Remove from cohort"
    action_name = "remove_from_cohort"
    variant = "error"
    confirm_variant = "error"
    loading_text = "Removing…"
    capability = DELETE_COHORTMEMBERSHIP
    unchanged_reason = "not a member"

    def skip_reason(self, obj: Model, cleaned_data: dict[str, object]) -> str | None:
        return None if obj.pk in self.staff_member_ids else self.unchanged_reason

    def perform(self, obj: Model, cleaned_data: dict[str, object], actor: User) -> bool:
        return remove_from_cohort(
            cast(Learner, obj), cast(Cohort, cleaned_data["cohort"]), actor=actor
        )

    def sentence(self, count: int, cleaned_data: dict[str, object]) -> str:
        cohort = cast(Cohort, cleaned_data["cohort"])
        return f"Remove {count_noun(Learner, count)} from {cohort.name}."

    def consequences(
        self,
        queryset: QuerySet,
        classified: dict[str, BulkOutcome] | None,
        cleaned_data: dict[str, object],
    ) -> list[str]:
        cohort = cast(Cohort, cleaned_data["cohort"])
        lost = courses_lost_by_any(
            queryset.filter(pk__in=self.changed_keys(classified)), cohort
        )
        if not lost:
            return []
        prefetch_related_objects(lost, "organisations")
        titles = join_prose([course.label_for(cohort.organisation) for course in lost])
        return [f"They lose access to: {titles}."]


class LearnerStateBulkAction(LearnerBulkAction):
    """Moves learners to `target_state`; learners already there are skipped."""

    capability = CHANGE_LEARNER
    target_state: bool

    def skip_reason(self, obj: Model, cleaned_data: dict[str, object]) -> str | None:
        if cast(Learner, obj).is_active == self.target_state:
            return self.unchanged_reason
        return None


@register_bulk_action
class DeactivateLearnersBulkAction(LearnerStateBulkAction):
    label = "Deactivate"
    action_name = "deactivate"
    variant = "secondary"
    loading_text = "Deactivating…"
    target_state = False
    unchanged_reason = "already inactive"

    def perform(self, obj: Model, cleaned_data: dict[str, object], actor: User) -> bool:
        return deactivate_learner(cast(Learner, obj), actor=actor)

    def sentence(self, count: int, cleaned_data: dict[str, object]) -> str:
        return f"Deactivate {count_noun(Learner, count)}."

    def consequences(
        self,
        queryset: QuerySet,
        classified: dict[str, BulkOutcome] | None,
        cleaned_data: dict[str, object],
    ) -> list[str]:
        return [
            "They lose access to this organisation's courses.",
            "Their cohorts, registrations and progress are kept and "
            "return when you reactivate them.",
        ]


@register_bulk_action
class ReactivateLearnersBulkAction(LearnerStateBulkAction):
    label = "Reactivate"
    action_name = "reactivate"
    loading_text = "Reactivating…"
    target_state = True
    unchanged_reason = "already active"

    def perform(self, obj: Model, cleaned_data: dict[str, object], actor: User) -> bool:
        return reactivate_learner(cast(Learner, obj), actor=actor)

    def sentence(self, count: int, cleaned_data: dict[str, object]) -> str:
        return f"Reactivate {count_noun(Learner, count)}."

    def consequences(
        self,
        queryset: QuerySet,
        classified: dict[str, BulkOutcome] | None,
        cleaned_data: dict[str, object],
    ) -> list[str]:
        return [
            "Their access returns through their existing cohorts and registrations."
        ]


class CourseRegistrationBulkAction(CoursePickerMixin, LearnerBulkAction):
    """Registers learners for, or unregisters them from, the one course the
    educator picks. `registered_ids` holds the selected learners with an
    active individual registration for it, read once per classification so
    previewing costs a fixed number of queries however many are selected."""

    registered_ids: frozenset[object] = frozenset()

    def classify_all(
        self,
        request: HttpRequest,
        queryset: QuerySet,
        cleaned_data: dict[str, object],
    ) -> dict[str, BulkOutcome] | None:
        self.registered_ids = frozenset(
            LearnerCourseRegistration.objects.filter(
                course=cleaned_data["course"], learner__in=queryset, is_active=True
            ).values_list("learner_id", flat=True)
        )
        return super().classify_all(request, queryset, cleaned_data)


@register_bulk_action
class RegisterForCourseBulkAction(CourseRegistrationBulkAction):
    label = "Register for a course"
    action_name = "register_for_course"
    loading_text = "Registering…"
    capability = ADD_LEARNERCOURSEREGISTRATION
    unchanged_reason = "already registered individually"

    def skip_reason(self, obj: Model, cleaned_data: dict[str, object]) -> str | None:
        return self.unchanged_reason if obj.pk in self.registered_ids else None

    def perform(self, obj: Model, cleaned_data: dict[str, object], actor: User) -> bool:
        return register_for_course(
            cast(Learner, obj), cast(Course, cleaned_data["course"]), actor=actor
        )

    def sentence(self, count: int, cleaned_data: dict[str, object]) -> str:
        return (
            f"Register {count_noun(Learner, count)} for {cleaned_data['course_label']}."
        )


@register_bulk_action
class DeactivateRegistrationBulkAction(CourseRegistrationBulkAction):
    label = "Deactivate a course registration"
    action_name = "deactivate_registration"
    variant = "secondary"
    loading_text = "Deactivating…"
    capability = CHANGE_LEARNERCOURSEREGISTRATION
    unchanged_reason = "not registered individually"

    def skip_reason(self, obj: Model, cleaned_data: dict[str, object]) -> str | None:
        return None if obj.pk in self.registered_ids else self.unchanged_reason

    def perform(self, obj: Model, cleaned_data: dict[str, object], actor: User) -> bool:
        return deactivate_registration(
            cast(Learner, obj), cast(Course, cleaned_data["course"]), actor=actor
        )

    def sentence(self, count: int, cleaned_data: dict[str, object]) -> str:
        return f"Deactivate the {cleaned_data['course_label']} registration for {count_noun(Learner, count)}."

    def consequences(
        self,
        queryset: QuerySet,
        classified: dict[str, BulkOutcome] | None,
        cleaned_data: dict[str, object],
    ) -> list[str]:
        keeping = learners_keeping_access_count(
            queryset.filter(pk__in=self.changed_keys(classified)),
            cast(Course, cleaned_data["course"]),
        )
        if not keeping:
            return []
        verb = "keeps" if keeping == 1 else "keep"
        return [f"{keeping} {verb} access through a cohort."]


@register_bulk_action
class ResendSetupEmailBulkAction(LearnerBulkAction):
    label = "Resend setup email"
    action_name = "resend_setup_email"
    loading_text = "Sending…"
    capability = CHANGE_LEARNER
    unchanged_reason = "account already set up"
    recently_sent_reason = "setup email sent recently"
    pending_ids: frozenset[object] = frozenset()

    def classify_all(
        self,
        request: HttpRequest,
        queryset: QuerySet,
        cleaned_data: dict[str, object],
    ) -> dict[str, BulkOutcome] | None:
        self.pending_ids = frozenset(
            queryset.filter(pending_user_q("user__")).values_list("pk", flat=True)
        )
        return super().classify_all(request, queryset, cleaned_data)

    def skip_reason(self, obj: Model, cleaned_data: dict[str, object]) -> str | None:
        return None if obj.pk in self.pending_ids else self.unchanged_reason

    def perform(self, obj: Model, cleaned_data: dict[str, object], actor: User) -> bool:
        record_and_resend_setup_email(cast(Learner, obj), actor)
        return True

    def apply(
        self,
        user: AbstractBaseUser | AnonymousUser,
        obj: Model,
        cleaned_data: dict[str, object],
    ) -> BulkOutcome:
        # Both refusals leave the learner as they were, so they are skips
        # with their own reasons rather than failures.
        try:
            return super().apply(user, obj, cleaned_data)
        except AccountAlreadySetUp:
            return BulkOutcome("skipped", self.unchanged_reason)
        except SetupEmailRecentlySent:
            return BulkOutcome("skipped", self.recently_sent_reason)

    def sentence(self, count: int, cleaned_data: dict[str, object]) -> str:
        return f"Resend the setup email to {count_noun(Learner, count)}."

    def result_line(self, item: BulkCount) -> str:
        if item.reason == self.unchanged_reason:
            return f"{count_noun(Learner, item.count)} already set up."
        if item.reason == self.recently_sent_reason:
            emails = count_phrase(item.count, "setup email was", "setup emails were")
            return f"{emails} sent recently."
        return super().result_line(item)

    def confirmation_skip_line(self, item: BulkCount) -> str:
        # "account already set up" names its own subject, so it cannot follow
        # the "N is/are" the default line puts in front of a reason.
        if item.reason == self.unchanged_reason:
            return (
                f"{count_noun(Learner, item.count)} "
                f"{'is' if item.count == 1 else 'are'} "
                "already set up and will be skipped."
            )
        return super().confirmation_skip_line(item)


class CohortBulkAction(EducatorBulkAction):
    """A bulk action over the rows of the cohorts table."""

    table_key = "cohorts"
    noun_model = Cohort

    def with_related(self, queryset: QuerySet) -> QuerySet:
        return queryset.select_related("organisation", "site")

    def permitted(
        self,
        user: AbstractBaseUser | AnonymousUser,
        scope: Model | None,
        queryset: QuerySet,
        cleaned_data: dict[str, object],
    ) -> QuerySet:
        return queryset.filter(
            pk__in=cohorts_visible_to(
                user, cast(Organisation, scope), capability=self.capability
            ).values("pk")
        )


class CohortCourseBulkAction(CoursePickerMixin, CohortBulkAction):
    """Registers cohorts for, or unregisters them from, the one course the
    educator picks. `registered_ids` holds the selected cohorts with an active
    registration for it, read once per classification so previewing costs a
    fixed number of queries however many cohorts are selected."""

    inactive_reason = "inactive"
    registered_ids: frozenset[object] = frozenset()

    def classify_all(
        self,
        request: HttpRequest,
        queryset: QuerySet,
        cleaned_data: dict[str, object],
    ) -> dict[str, BulkOutcome] | None:
        self.registered_ids = frozenset(
            CohortCourseRegistration.objects.filter(
                course=cleaned_data["course"], cohort__in=queryset, is_active=True
            ).values_list("cohort_id", flat=True)
        )
        return super().classify_all(request, queryset, cleaned_data)

    def skip_reason(self, obj: Model, cleaned_data: dict[str, object]) -> str | None:
        if not cast(Cohort, obj).is_active:
            return self.inactive_reason
        return self.state_skip_reason(obj.pk in self.registered_ids)

    def apply(
        self,
        user: AbstractBaseUser | AnonymousUser,
        obj: Model,
        cleaned_data: dict[str, object],
    ) -> BulkOutcome:
        # Permission first, as the preview checks it, so both give one reason.
        if obj.pk in self.permitted_ids and not cast(Cohort, obj).is_active:
            return BulkOutcome("skipped", self.inactive_reason)
        return super().apply(user, obj, cleaned_data)

    def state_skip_reason(self, is_registered: bool) -> str | None:
        """The skip reason for an active cohort, given whether it holds an
        active registration for the course."""
        raise NotImplementedError


@register_bulk_action
class RegisterCohortForCourseBulkAction(CohortCourseBulkAction):
    label = "Register for a course"
    action_name = "register"
    loading_text = "Registering…"
    capability = ADD_COHORTCOURSEREGISTRATION
    unchanged_reason = "already registered"

    def state_skip_reason(self, is_registered: bool) -> str | None:
        return self.unchanged_reason if is_registered else None

    def perform(self, obj: Model, cleaned_data: dict[str, object], actor: User) -> bool:
        return register_cohort_for_course(
            cast(Cohort, obj), cast(Course, cleaned_data["course"]), actor=actor
        )

    def sentence(self, count: int, cleaned_data: dict[str, object]) -> str:
        return (
            f"Register {count_noun(Cohort, count)} for {cleaned_data['course_label']}."
        )


@register_bulk_action
class DeactivateCohortRegistrationBulkAction(CohortCourseBulkAction):
    label = "Deactivate a course registration"
    action_name = "deactivate_cohort_registration"
    variant = "secondary"
    loading_text = "Deactivating…"
    capability = CHANGE_COHORTCOURSEREGISTRATION
    unchanged_reason = "not registered"

    def state_skip_reason(self, is_registered: bool) -> str | None:
        return None if is_registered else self.unchanged_reason

    def perform(self, obj: Model, cleaned_data: dict[str, object], actor: User) -> bool:
        registration = (
            CohortCourseRegistration._base_manager.filter(
                cohort=cast(Cohort, obj),
                course=cast(Course, cleaned_data["course"]),
                is_active=True,
            )
            .select_related("cohort", "course")
            .first()
        )
        if registration is None:
            return False
        return deactivate_cohort_registration(registration, actor=actor)

    def sentence(self, count: int, cleaned_data: dict[str, object]) -> str:
        return f"Deactivate the {cleaned_data['course_label']} registration for {count_noun(Cohort, count)}."

    def consequences(
        self,
        queryset: QuerySet,
        classified: dict[str, BulkOutcome] | None,
        cleaned_data: dict[str, object],
    ) -> list[str]:
        return [
            "Learners in these cohorts lose access to the course unless "
            "they have another registration for it."
        ]


class CohortStateBulkAction(CohortBulkAction):
    """Moves cohorts to `target_state`; cohorts already there are skipped."""

    capability = CHANGE_COHORT
    target_state: bool

    def skip_reason(self, obj: Model, cleaned_data: dict[str, object]) -> str | None:
        if cast(Cohort, obj).is_active == self.target_state:
            return self.unchanged_reason
        return None


@register_bulk_action
class DeactivateCohortsBulkAction(CohortStateBulkAction):
    label = "Deactivate"
    action_name = "deactivate"
    variant = "secondary"
    loading_text = "Deactivating…"
    target_state = False
    unchanged_reason = "already inactive"

    def perform(self, obj: Model, cleaned_data: dict[str, object], actor: User) -> bool:
        return deactivate_cohort(cast(Cohort, obj), actor=actor)

    def sentence(self, count: int, cleaned_data: dict[str, object]) -> str:
        return f"Deactivate {count_noun(Cohort, count)}."

    def consequences(
        self,
        queryset: QuerySet,
        classified: dict[str, BulkOutcome] | None,
        cleaned_data: dict[str, object],
    ) -> list[str]:
        return [
            "Learners stay in their cohorts and keep their progress.",
            "While a cohort is inactive, its registrations stop giving "
            "access to its courses. Learners with another registration "
            "for a course keep access to it.",
            "You can reactivate a cohort at any time.",
        ]


@register_bulk_action
class ReactivateCohortsBulkAction(CohortStateBulkAction):
    label = "Reactivate"
    action_name = "reactivate"
    loading_text = "Reactivating…"
    target_state = True
    unchanged_reason = "already active"

    def perform(self, obj: Model, cleaned_data: dict[str, object], actor: User) -> bool:
        return reactivate_cohort(cast(Cohort, obj), actor=actor)

    def sentence(self, count: int, cleaned_data: dict[str, object]) -> str:
        return f"Reactivate {count_noun(Cohort, count)}."

    def consequences(
        self,
        queryset: QuerySet,
        classified: dict[str, BulkOutcome] | None,
        cleaned_data: dict[str, object],
    ) -> list[str]:
        if self.changed_count(classified) == 1:
            return ["It gives access to its courses again."]
        return ["They give access to their courses again."]
