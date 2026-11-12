"""Panel actions on a cohort that need more than the generic framework ones."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import TYPE_CHECKING, NamedTuple, cast
from uuid import UUID

from django import forms
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.db import transaction
from django.db.models import Model, QuerySet
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseNotAllowed,
    QueryDict,
)
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode

from freedom_ls.accounts.account_setup import (
    AccountAlreadySetUp,
    EmailInUseOnAnotherSite,
    SetupEmailRecentlySent,
    is_pending,
    lookup_user,
    match_or_create_user,
    pending_user_q,
    resend_account_setup_email,
    send_account_setup_email,
)
from freedom_ls.accounts.config import config as accounts_config
from freedom_ls.accounts.models import User, display_name_for
from freedom_ls.accounts.search import MIN_TERM_LENGTH, term_condition
from freedom_ls.comms.notify import mark_notifications_read, raise_notification
from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.events import (
    COHORT_CHANGED,
    LEARNER_CHANGED,
    REGISTRATION_CHANGED,
    STAFF_CHANGED,
)
from freedom_ls.educator_interface.filters import may_see_staff_roles
from freedom_ls.educator_interface.forms import (
    AddLearnerForm,
    AddStaffMemberForm,
    BulkTargetPickerForm,
    ChangeRoleForm,
    CohortCourseRegistrationForm,
    CohortPickerForm,
    CohortSetForm,
    EducatorReasonForm,
    LearnerCourseRegistrationForm,
    LearnerNameForm,
    LearnerPickerForm,
    StaffEmailForm,
    choice_error,
)
from freedom_ls.educator_interface.learner_import import check_import_gate
from freedom_ls.educator_interface.staff import (
    ORGANISATION_SCOPE,
    RoleEntry,
    current_role_entries,
)
from freedom_ls.educator_interface.user_display import email_below_name
from freedom_ls.learner_management.capabilities import _active_role_assignments, can
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
    StaffMember,
)
from freedom_ls.learner_management.queries import (
    ADD_COHORTCOURSEREGISTRATION,
    ADD_COHORTMEMBERSHIP,
    ADD_LEARNER,
    ADD_LEARNERCOURSEREGISTRATION,
    ADD_STAFF_MEMBER,
    ASSIGN_COHORT_VIEWER,
    CHANGE_COHORT,
    CHANGE_COHORTCOURSEREGISTRATION,
    CHANGE_LEARNER,
    CHANGE_LEARNERCOURSEREGISTRATION,
    DELETE_COHORTMEMBERSHIP,
    ORGANISATION_ROLES,
    STAFF_ROLES,
    CourseNotOpenError,
    can_on_any,
    cohort_course_count,
    cohort_is_empty,
    cohort_learner_count,
    cohorts_visible_to,
    courses_gaining_access,
    courses_losing_access,
    courses_lost_by_any,
    has_staff_assignments,
    import_into_cohort_in_progress,
    learners_keeping_access_count,
    learners_permitted_for,
    learners_visible_to,
    members_keeping_access,
    other_grants_for,
    pickable_staff,
    registerable_courses,
    role_target,
    staff_assignments,
    staff_of,
)
from freedom_ls.learner_management.role_assignment import (
    ASSIGN,
    CHANGE_STAFF_MEMBER,
    GrantableRole,
    add_staff_member,
    assign_role,
    deactivate_role,
    grantable_roles,
    is_last_organisation_admin,
    is_site_level_admin,
    set_staff_member_active,
)
from freedom_ls.learner_management.utils import (
    deactivate_cohort_registration,
    ensure_staff_member,
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
    ReasonMixin,
    changed_response,
    count_noun,
    count_phrase,
    current_page_within,
    denied_response,
    field_error_count,
    form_fragment_context,
    join_prose,
    navigation_response,
    refusal_response,
)
from freedom_ls.panel_framework.bulk_actions import (
    BulkCount,
    BulkOutcome,
    ConfirmationWording,
    RecordedBulkAction,
    count_outcomes,
)
from freedom_ls.panel_framework.bulk_runs import run_summary
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.events import build_hx_trigger
from freedom_ls.panel_framework.models import BulkActionRun
from freedom_ls.role_based_permissions.exceptions import (
    RefusalReason,
    RoleChangeRefused,
)
from freedom_ls.role_based_permissions.loader import get_role_config
from freedom_ls.role_based_permissions.models import ObjectRoleAssignment
from freedom_ls.role_based_permissions.utils import delete_role_rows_for

if TYPE_CHECKING:
    from freedom_ls.educator_interface.views import OrganisationScopedRequest


def grantable_roles_for(request: HttpRequest) -> list[GrantableRole]:
    """The grantor's grantable roles in the request's organisation, computed
    once and kept on the request, so every cell and action on a page reads
    the same list."""
    scoped = cast("OrganisationScopedRequest", request)
    cached = getattr(scoped, "grantable_roles", None)
    if cached is None:
        cached = grantable_roles(cast("User", scoped.user), scoped.organisation)
        scoped.grantable_roles = cached
    return cached


def roles_grantable_on(request: HttpRequest, cohort: Cohort) -> set[str]:
    """The role keys the grantor may give or take on this cohort."""
    return {
        grantable.role
        for grantable in grantable_roles_for(request)
        if grantable.cohorts is not None and cohort in grantable.cohorts
    }


def role_reach(request: HttpRequest, role: str) -> set[Cohort]:
    """The cohorts the grantor may give or take `role` on, inactive ones
    included, computed once per role and kept on the request."""
    scoped = cast("OrganisationScopedRequest", request)
    cached: dict[str, set[Cohort]] | None = getattr(scoped, "role_reach", None)
    if cached is None:
        cached = {}
        scoped.role_reach = cached
    if role not in cached:
        cached[role] = set(
            cohorts_visible_to(
                cast("User", scoped.user),
                scoped.organisation,
                capability=ASSIGN.format(role=role),
            )
        )
    return cached[role]


def actionable_roles(request: HttpRequest, entries: list[RoleEntry]) -> set[str]:
    """The roles among `entries` the grantor may deactivate or change: an
    organisation role they may give, and a cohort role held on at least one
    cohort within their reach."""
    grantable = {g.role for g in grantable_roles_for(request)}
    return {
        entry.role
        for entry in entries
        if entry.role in grantable
        and (
            entry.target == "organisation"
            or any(
                cohort in role_reach(request, entry.role) for cohort in entry.cohorts
            )
        )
    }


def role_entries_shown_to(
    request: HttpRequest, entries: list[RoleEntry]
) -> list[RoleEntry]:
    """The part of a person's roles the viewer may read. A viewer who may see
    staff roles reads them all. Anyone else reads a cohort role on the cohorts
    they may give it on, which that cohort's own Staff list already shows
    them, and no organisation role."""
    if may_see_staff_roles(request):
        return entries
    reach = {
        grantable.role: set(grantable.cohorts)
        for grantable in grantable_roles_for(request)
        if grantable.cohorts is not None
    }
    trimmed = (
        replace(
            entry,
            cohorts=tuple(c for c in entry.cohorts if c in reach.get(entry.role, ())),
        )
        for entry in entries
    )
    return [entry for entry in trimmed if entry.cohorts]


def has_grantable_roles(ctx: PanelContext) -> bool:
    """Whether the viewer may give any staff role here. The organisation-level
    can() is false for a cohort admin, so the per-entry actions ask this
    instead and assign_role / deactivate_role re-check each target."""
    return bool(grantable_roles_for(ctx.request))


def _uuid_from(params: Mapping[str, str], name: str) -> UUID:
    try:
        return UUID(params.get(name, ""))
    except ValueError:
        raise Http404(f"No such {name}") from None


def _action_params(request: HttpRequest) -> Mapping[str, str]:
    """The parameters an action's trigger sent along: the form on a submit,
    the query string otherwise."""
    return request.POST if request.method == "POST" else request.GET


def _uuid_param(request: HttpRequest, name: str) -> UUID:
    """A UUID the action's trigger sent along. A missing or malformed value is
    a 404."""
    return _uuid_from(_action_params(request), name)


def _staff_member_param(ctx: PanelContext) -> User:
    """The staff member named by the action's `user` parameter. A
    missing, malformed or non-staff value is a 404."""
    try:
        pk = int(_action_params(ctx.request).get("user", ""))
    except ValueError:
        raise Http404("No such user") from None
    return get_object_or_404(staff_of(_organisation(ctx)), pk=pk)


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


class EducatorReasonMixin(ReasonMixin):
    """A reason dialog that words its field the educator way."""

    reason_form_class = EducatorReasonForm


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

    def form_valid(self, request: HttpRequest, form: forms.ModelForm) -> HttpResponse:
        old_name = str(form.initial["name"])
        with transaction.atomic():
            response = super().form_valid(request, form)
            if "name" in form.changed_data:
                cohort = cast(Cohort, form.instance)
                record_cohort_entry(
                    cohort,
                    "cohort.renamed",
                    cast("User", request.user),
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

    def get_form(
        self, request: HttpRequest, instance: Model | None = None
    ) -> forms.ModelForm:
        # The page's instance is the learner; the form edits their user.
        return super().get_form(request, self._instance)

    def event_instance(self, form: forms.ModelForm) -> Model:
        return self._learner

    def form_valid(self, request: HttpRequest, form: forms.ModelForm) -> HttpResponse:
        # The form has already bound the new names onto the user; its initial
        # data still holds the stored ones.
        user = cast("User", form.instance)
        old_name = display_name_for(
            form.initial["first_name"], form.initial["last_name"], user.email
        )
        with transaction.atomic():
            response = super().form_valid(request, form)
            if {"first_name", "last_name"} & set(form.changed_data):
                record_learner_entry(
                    self._learner,
                    "learner.renamed",
                    cast("User", request.user),
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
    blocked_phrase = "deactivate it"
    target_state = False
    loading_text = "Deactivating…"
    template_name = "educator_interface/modal/deactivate_confirmation.html"

    def perform(self, cohort: Cohort, *, actor: User, reason: str) -> bool:
        return deactivate_cohort(cohort, actor=actor, reason=reason)

    def refuse_unchanged(self, ctx: PanelContext, cohort: Cohort) -> HttpResponse:
        return inactive_cohort_response(ctx, cohort, self.blocked_phrase)


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

    def get_confirm_context(self, ctx: PanelContext) -> dict[str, object]:
        cohort = cast(Cohort, ctx.instance)
        reason = cohort_not_empty_sentence(cohort)
        if reason:
            return {
                **super().get_confirm_context(ctx),
                "cascade_summary": [],
                "blocked_reason": reason,
            }
        return super().get_confirm_context(ctx)

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
    submit_buttons = [
        {"label": "Register", "variant": "primary", "loading_text": "Registering…"}
    ]
    _cohort: Cohort
    _page_url: str

    def _bind(self, ctx: PanelContext) -> None:
        self._cohort = cast(Cohort, ctx.instance)
        self._page_url = ctx.page_url

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
        if request.method == "POST":
            return CohortCourseRegistrationForm(request.POST, cohort=self._cohort)
        return _picker_on_get(
            lambda data: CohortCourseRegistrationForm(data, cohort=self._cohort),
            request,
            "course",
        )

    def _fragment_context(
        self, form: forms.ModelForm, form_url: str
    ) -> dict[str, object]:
        _prepare_register_dialog(self, form, form_url, str(self._cohort))
        return super()._fragment_context(form, form_url)

    def form_valid(self, request: HttpRequest, form: forms.ModelForm) -> HttpResponse:
        register_cohort_for_course(
            self._cohort,
            form.cleaned_data["course"],
            actor=cast("User", request.user),
        )
        # The courses tab, its count and the header's course stat all
        # re-render, which a panel refresh alone could not do for the header.
        return navigation_response(self._page_url)


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

    def _registration(self, ctx: PanelContext) -> CohortCourseRegistration:
        return get_object_or_404(
            cast(Cohort, ctx.instance).course_registrations.select_related("course"),
            pk=_uuid_param(ctx.request, "registration"),
            is_active=True,
        )

    def get_hidden_fields(self, ctx: PanelContext) -> dict[str, str]:
        return {"registration": str(_uuid_param(ctx.request, "registration"))}

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
    submit_buttons = [
        {"label": "Register", "variant": "primary", "loading_text": "Registering…"}
    ]
    _learner: Learner

    def _bind(self, ctx: PanelContext) -> None:
        self._learner = cast(Learner, ctx.instance)

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        self._bind(ctx)
        context = super().get_context_data(ctx)
        context["empty_message"] = _empty_message(
            cast(forms.BaseForm, context["form"]),
            "course",
            f"There is no course {self._learner.user.display_name} can be "
            "registered for right now.",
        )
        return context

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        self._bind(ctx)
        return super().handle_submit(ctx)

    def get_form(
        self, request: HttpRequest, instance: Model | None = None
    ) -> forms.ModelForm:
        # On a POST, instance is the learner, which must never reach a
        # registration form.
        if request.method == "POST":
            return LearnerCourseRegistrationForm(request.POST, learner=self._learner)
        return _picker_on_get(
            lambda data: LearnerCourseRegistrationForm(data, learner=self._learner),
            request,
            "course",
        )

    def _fragment_context(
        self, form: forms.ModelForm, form_url: str
    ) -> dict[str, object]:
        _prepare_register_dialog(self, form, form_url, self._learner.user.display_name)
        return super()._fragment_context(form, form_url)

    def form_valid(self, request: HttpRequest, form: forms.ModelForm) -> HttpResponse:
        register_for_course(
            self._learner,
            form.cleaned_data["course"],
            actor=cast("User", request.user),
        )
        return _registration_changed_response(self._learner)


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

    def _registration(self, ctx: PanelContext) -> LearnerCourseRegistration:
        registrations = LearnerCourseRegistration.objects.filter(
            learner=cast(Learner, ctx.instance), is_active=True
        ).select_related("course")
        return cast(
            LearnerCourseRegistration,
            get_object_or_404(
                registrations, pk=_uuid_param(ctx.request, "registration")
            ),
        )

    def get_hidden_fields(self, ctx: PanelContext) -> dict[str, str]:
        return {"registration": str(_uuid_param(ctx.request, "registration"))}

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

    def _registration(self, ctx: PanelContext) -> LearnerCourseRegistration:
        registrations = LearnerCourseRegistration.objects.filter(
            learner=cast(Learner, ctx.instance), is_active=False
        ).select_related("course")
        return cast(
            LearnerCourseRegistration,
            get_object_or_404(
                registrations, pk=_uuid_param(ctx.request, "registration")
            ),
        )

    def get_hidden_fields(self, ctx: PanelContext) -> dict[str, str]:
        return {"registration": str(_uuid_param(ctx.request, "registration"))}

    def get_confirm_context(self, ctx: PanelContext) -> dict[str, object]:
        registration = self._registration(ctx)
        return {
            "learner": cast(Learner, ctx.instance),
            "registration": registration,
            "course": registration.course,
        }

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        learner = cast(Learner, ctx.instance)
        try:
            register_for_course(
                learner,
                self._registration(ctx).course,
                actor=cast("User", ctx.request.user),
            )
        except CourseNotOpenError as error:
            # The course may have gained organisations since the registration
            # was made, leaving it closed to this learner's organisation.
            context = self.get_context_data(ctx)
            context["refusal"] = str(error)
            return render(ctx.request, self.template_name, context, status=422)
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


def _cohort_picker(
    ctx: PanelContext,
    learner: Learner,
    get_data: Mapping[str, str] | None,
    *,
    field_name: str = "cohort",
) -> CohortPickerForm:
    """The picker of cohorts to put `learner` in, bound to `get_data` on a GET.

    A POST picks from every cohort of the organisation the learner is not in,
    wider than the offered set, so a cohort the user may see but not add to
    reaches the permission check and is refused as a denial.
    """
    if ctx.request.method == "POST":
        scoped = cast("OrganisationScopedRequest", ctx.request)
        queryset = Cohort.objects.filter(organisation=scoped.organisation).exclude(
            cohortmembership__learner=learner
        )
        data: Mapping[str, str] | None = ctx.request.POST
    else:
        queryset = _joinable_cohorts(ctx, learner)
        data = get_data
    return CohortPickerForm(data, queryset=queryset, field_name=field_name)


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

    def perform(
        self, learner: Learner, cohort: Cohort, actor: User, reason: str = ""
    ) -> bool:
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
                    scoped.user, scoped.organisation, include_inactive=True
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
        name = "learner" if isinstance(ctx.instance, Cohort) else "cohort"
        return {name: str(_uuid_param(ctx.request, name))}

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


def _empty_message(form: forms.BaseForm, field_name: str, message: str) -> str | None:
    """`message` when the picker's field offers nothing, otherwise None."""
    queryset = cast(forms.ModelChoiceField, form.fields[field_name]).queryset
    return None if queryset is not None and queryset.exists() else message


def _refresh_on_change(form: forms.BaseForm, field_name: str, url: str) -> None:
    """Make choosing a value re-render the dialog from `url`, so the title
    can name the choice before anything is submitted. Without JavaScript the
    title keeps its generic form and the submit still works."""
    form.fields[field_name].widget.attrs.update(
        {
            "hx-get": url,
            "hx-include": "closest form",
            "hx-trigger": "change",
            "hx-target": "#app-modal-body",
            "hx-swap": "innerHTML",
        }
    )


def _picker_on_get[F: forms.BaseForm](
    build: Callable[[Mapping[str, str] | None], F],
    request: HttpRequest,
    field_name: str,
) -> F:
    """The picker a GET renders: bound to the choice the query names when
    the picker offers it, else unbound. A stale choice is not a submission,
    so it earns no error."""
    if field_name in request.GET:
        form = build(request.GET)
        if form.is_valid():
            return form
    return build(None)


def _picker_title[M: Model](
    form: forms.BaseForm,
    field_name: str,
    *,
    unchosen: str,
    chosen: Callable[[M], str],
) -> str:
    """The question a picker dialog asks: `chosen` names the valid choice the
    form holds, `unchosen` stands until there is one."""
    if form.is_bound and form.is_valid():
        return f"{chosen(cast(M, form.cleaned_data[field_name]))}?"
    return f"{unchosen}?"


def _prepare_register_dialog(
    action: FormPanelAction, form: forms.BaseForm, form_url: str, subject: str
) -> None:
    """Title a register-for-a-course dialog for `subject` (a learner's or a
    cohort's name) and make its course select re-render it."""

    def chosen(course: Course) -> str:
        return f"Register {subject} for {course.title}"

    action.form_title = _picker_title(
        form, "course", unchosen=f"Register {subject} for a course", chosen=chosen
    )
    _refresh_on_change(form, "course", form_url)


def _picker_fragment(
    action: PanelAction,
    ctx: PanelContext,
    form: forms.BaseForm,
    *,
    title: str,
    button: dict[str, str],
    status: int = 200,
) -> HttpResponse:
    """The picker form's modal fragment, bound or unbound."""
    context = form_fragment_context(
        form,
        form_title=title,
        form_url=action.get_action_url(ctx),
        submit_buttons=[button],
    )
    html = render_to_string(
        "panel_framework/modal/form.html", context, request=ctx.request
    )
    return HttpResponse(html, status=status)


class AddToCohortAction(ModalPanelAction):
    """Adds the learner on the page to an active cohort the user may add to."""

    label = "Add to cohort"
    action_name = "add_to_cohort"
    variant = "secondary"
    capability = ADD_COHORTMEMBERSHIP
    template_name = "panel_framework/modal/form.html"
    _BUTTON = {
        "label": "Add to cohort",
        "variant": "primary",
        "loading_text": "Adding…",
    }

    def _form(self, ctx: PanelContext) -> CohortPickerForm:
        learner = cast(Learner, ctx.instance)
        if ctx.request.method == "POST":
            form = _cohort_picker(ctx, learner, None)
        else:
            form = _picker_on_get(
                lambda data: _cohort_picker(ctx, learner, data), ctx.request, "cohort"
            )
        _refresh_on_change(form, "cohort", self.get_action_url(ctx))
        return form

    def _title(self, ctx: PanelContext, form: CohortPickerForm) -> str:
        name = cast(Learner, ctx.instance).user.display_name

        def chosen(cohort: Cohort) -> str:
            return f"Add {name} to {cohort.name}"

        return _picker_title(
            form, "cohort", unchosen=f"Add {name} to a cohort", chosen=chosen
        )

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        form = self._form(ctx)
        name = cast(Learner, ctx.instance).user.display_name
        return form_fragment_context(
            form,
            form_title=self._title(ctx, form),
            form_url=self.get_action_url(ctx),
            submit_buttons=[self._BUTTON],
            empty_message=_empty_message(
                form,
                "cohort",
                f"{name} is already in every active cohort you can add learners to.",
            ),
        )

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        form = self._form(ctx)
        if not form.is_valid():
            return _picker_fragment(
                self,
                ctx,
                form,
                title=self._title(ctx, form),
                button=self._BUTTON,
                status=422,
            )
        cohort = cast(Cohort, form.cleaned_data["cohort"])
        if not can(ctx.request.user, ADD_COHORTMEMBERSHIP, cohort):
            return denied_response(ctx, self)
        if not cohort.is_active:
            return inactive_cohort_response(ctx, cohort, "add learners to it")
        learner = cast(Learner, ctx.instance)
        add_to_cohort(learner, cohort, actor=cast("User", ctx.request.user))
        return _membership_changed_response([str(learner.pk)], [str(cohort.pk)])


class AddExistingLearnersAction(RequiresActiveCohortMixin, ModalPanelAction):
    """Adds existing learners to the cohort on the page, for a user who may
    add cohort members but not create learners."""

    label = "Add learners"
    action_name = "add_existing_learners"
    blocked_phrase = "add learners to it"
    variant = "secondary"
    capability = ADD_COHORTMEMBERSHIP
    template_name = "panel_framework/modal/form.html"
    _BUTTON = {
        "label": "Add learners",
        "variant": "primary",
        "loading_text": "Adding…",
    }

    def is_offered(self, ctx: PanelContext) -> bool:
        scoped = cast("OrganisationScopedRequest", ctx.request)
        return super().is_offered(ctx) and not can(
            scoped.user, ADD_LEARNER, scoped.organisation
        )

    def _form(self, ctx: PanelContext) -> LearnerPickerForm:
        scoped = cast("OrganisationScopedRequest", ctx.request)
        cohort = cast(Cohort, ctx.instance)
        return LearnerPickerForm(
            ctx.request.POST if ctx.request.method == "POST" else None,
            queryset=learners_visible_to(scoped.user, scoped.organisation)
            .select_related("user")
            .exclude(cohortmembership__cohort=cohort),
        )

    def _title(self, ctx: PanelContext) -> str:
        return f"Add learners to {cast(Cohort, ctx.instance)}"

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        form = self._form(ctx)
        return form_fragment_context(
            form,
            form_title=self._title(ctx),
            form_url=self.get_action_url(ctx),
            submit_buttons=[self._BUTTON],
            empty_message=_empty_message(
                form,
                "learners",
                f"Everyone in your other cohorts is already in {ctx.instance}. "
                "To add someone new, ask an organisation admin.",
            ),
        )

    def handle_active_submit(self, ctx: PanelContext) -> HttpResponse:
        form = self._form(ctx)
        if not form.is_valid():
            return _picker_fragment(
                self, ctx, form, title=self._title(ctx), button=self._BUTTON, status=422
            )
        cohort = cast(Cohort, ctx.instance)
        learners = form.cleaned_data["learners"]
        with transaction.atomic():
            for learner in learners:
                add_to_cohort(learner, cohort, actor=cast("User", ctx.request.user))
        return _membership_changed_response(
            [str(learner.pk) for learner in learners], [str(cohort.pk)]
        )


class AddLearnerAction(ModalPanelAction):
    """Adds one email address as a learner of the organisation, making a
    pending account for an unknown address, and optionally puts them in a
    cohort. Add reports the outcome in the modal with Add another beside
    Close; Add and add another reports it above an empty form with the
    cohort kept, so a handful of people are added one at a time. A list of
    people is the file import."""

    label = "Add learner"
    action_name = "add_learner"
    capability = ADD_LEARNER
    template_name = "panel_framework/modal/form.html"
    _BUTTONS = [
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
        return get_object_or_404(
            self._cohorts(ctx), pk=_uuid_from(ctx.request.GET, "cohort")
        )

    def _form(
        self, ctx: PanelContext, preset: Cohort | None, *, bound: bool = True
    ) -> AddLearnerForm:
        return AddLearnerForm(
            ctx.request.POST if bound and ctx.request.method == "POST" else None,
            cohorts=self._cohorts(ctx),
            preset=preset,
        )

    def _form_url(self, ctx: PanelContext, preset: Cohort | None) -> str:
        url = self.get_action_url(ctx)
        if preset is not None and not isinstance(ctx.instance, Cohort):
            return f"{url}?cohort={preset.pk}"
        return url

    def _fragment_context(
        self,
        ctx: PanelContext,
        form: AddLearnerForm,
        preset: Cohort | None,
        status_message: str = "",
    ) -> dict[str, object]:
        return {
            **form_fragment_context(
                form,
                form_title=f"Add a learner to {preset}" if preset else "Add a learner",
                form_url=self._form_url(ctx, preset),
                submit_buttons=self._BUTTONS,
            ),
            "status_message": status_message,
        }

    @staticmethod
    def _outcome_sentence(result: AddLearnerResult) -> str:
        sentence = f"{result.email}: {result.outcome.label}."
        if result.cohort_outcome:
            sentence += f" {result.cohort_outcome.label}."
        return sentence

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        preset = self._preset_cohort(ctx)
        return self._fragment_context(ctx, self._form(ctx, preset), preset)

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        preset = self._preset_cohort(ctx)
        form = self._form(ctx, preset)
        if not form.is_valid():
            html = render_to_string(
                self.template_name,
                self._fragment_context(ctx, form, preset),
                request=ctx.request,
            )
            return HttpResponse(html, status=422)
        cohort = cast(Cohort | None, form.cleaned_data["cohort"]) or preset
        organisation = cast("OrganisationScopedRequest", ctx.request).organisation
        try:
            result = add_learner(
                organisation,
                form.entry(),
                cohort,
                actor=cast("User", ctx.request.user),
            )
        except CohortUnavailableError:
            return inactive_cohort_response(
                ctx, cast(Cohort, cohort), "add learners to it"
            )
        if ctx.request.POST.get("action") == "add_another":
            html = render_to_string(
                self.template_name,
                self._fragment_context(
                    ctx,
                    self._form(ctx, preset, bound=False),
                    preset,
                    status_message=self._outcome_sentence(result),
                ),
                request=ctx.request,
            )
        else:
            html = render_to_string(
                "educator_interface/modal/add_learner_result.html",
                {
                    "result": result,
                    "added": result.outcome in self._ADDED,
                    "cohort": cohort,
                    "form_url": self._form_url(ctx, preset),
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


#: The in-dialog message for each refusal the interface can show. NOT_PERMITTED is
#: the 403 denied fragment instead, and LAST_SITE_ADMIN cannot arise, because
#: site_admin is never granted or removed from here, so a KeyError on it is a bug.
REFUSAL_MESSAGES: dict[RefusalReason, str] = {
    RefusalReason.INACTIVE_USER: (
        "This person's account is turned off, so they can't be given a role."
    ),
    RefusalReason.SELF: (
        "You can't change your own roles. Ask another organisation admin."
    ),
    RefusalReason.LAST_ORGANISATION_ADMIN: (
        "{name} is this organisation's only organisation admin. "
        "Add another organisation admin first."
    ),
    RefusalReason.ALREADY_STAFF: "{name} is already on the staff here.",
    RefusalReason.INACTIVE_STAFF_MEMBER: (
        "{name} is an inactive staff member here. Use Reactivate staff member instead."
    ),
    RefusalReason.NOT_VISIBLE: (
        "No staff member you can add has this email. "
        "Ask an organisation admin to add them."
    ),
}

SEARCH_LISTBOX_ID = "staff-search-listbox"
OTHER_SITE_MESSAGE = (
    "This address belongs to an account on another site. Use a different address."
)


def _organisation(ctx: PanelContext) -> Organisation:
    return cast("OrganisationScopedRequest", ctx.request).organisation


def _refused(ctx: PanelContext, message: str) -> HttpResponse:
    """The 422 message a staff dialog shows in place of its body."""
    return refusal_response(ctx, title="This change wasn't made", message=message)


def role_refusal_response(
    ctx: PanelContext, action: PanelAction, refused: RoleChangeRefused, name: str
) -> HttpResponse:
    """What a refused role change answers with: the 403 denied fragment for
    a missing capability, else a 422 message inside the dialog."""
    if refused.reason == RefusalReason.NOT_PERMITTED:
        return denied_response(ctx, action)
    return _refused(ctx, REFUSAL_MESSAGES[refused.reason].format(name=name))


def _staff_member_name(user: User | None, email: str) -> str:
    """What the dialog calls the person: their name, or the address of an
    account not yet created."""
    return email if user is None else user.display_name


def staff_member_changed_response(user: User, ctx: PanelContext) -> HttpResponse:
    """The changed response. When the change took away the actor's own access
    to the section the action was posted from (they removed their own
    Organisation admin on Staff), it also sends them to the first section
    they can still see, or the educator root when none shows, so they are
    not left on a page that now 404s."""
    from freedom_ls.educator_interface.views import interface_config
    from freedom_ls.panel_framework.views import first_visible_section

    response = changed_response({STAFF_CHANGED: [str(user.pk)]})
    request = ctx.request
    # Visibility answers cached earlier in this request predate the change.
    for cached in ("works_with_cohorts", "may_see_staff_roles"):
        vars(request).pop(cached, None)
    if ctx.config.is_visible(request) and ctx.config.is_available(request):
        return response
    landing = first_visible_section(interface_config, request)
    if landing is None:
        response["HX-Redirect"] = reverse("educator_interface:root")
    else:
        response["HX-Redirect"] = reverse(
            "educator_interface:interface",
            kwargs={
                "organisation_slug": cast(
                    "OrganisationScopedRequest", request
                ).organisation.slug,
                "path_string": landing.url_name,
            },
        )
    return response


def staff_member_state(user: User | None, organisation: Organisation) -> str:
    """Where a role given now would land: "new" for an account not yet
    created, "missing" for one with no StaffMember row here,
    "inactive" for an inactive row, else "active"."""
    if user is None:
        return "new"
    staff_member = StaffMember.objects.filter(
        organisation=organisation, user=user
    ).first()
    if staff_member is None:
        return "missing"
    if not staff_member.is_active:
        return "inactive"
    return "active"


def _entries_after(
    before: list[RoleEntry],
    grantor: User,
    role: str,
    display_name: str,
    cohorts: list[Cohort],
) -> list[RoleEntry]:
    """`before` with `role` on `cohorts` merged in, in STAFF_ROLES order."""
    held = {entry.role: entry for entry in before}
    existing = held.get(role)
    merged = {*(existing.cohorts if existing else ()), *cohorts}
    held[role] = RoleEntry(
        role=role,
        display_name=display_name,
        cohorts=tuple(sorted(merged, key=lambda c: c.name)),
        assigned_by=grantor,
        assigned_at=timezone.now(),
    )
    return [held[key] for key in STAFF_ROLES if key in held]


class AddStaffMemberAction(ModalPanelAction):
    """Gives an existing account a staff role, in a dialog of steps: look up
    the address, choose the role, confirm. Nothing is written until the
    confirmation is submitted."""

    label = "Add staff member"
    action_name = "add_staff_member"
    capability = ADD_STAFF_MEMBER
    template_name = "educator_interface/modal/add_staff_member.html"
    #: Every role this dialog could offer. A role missing from the grantor's
    #: grantable roles counts as withheld only when it is in here.
    offerable_roles: tuple[str, ...] = STAFF_ROLES
    #: Whether the dialog may add someone to the staff with no role.
    offers_no_role: bool = True
    SEARCH_RESULT_LIMIT = 8

    def permission_object(self, ctx: PanelContext) -> Model | None:
        return _organisation(ctx)

    def _may_add_anyone(self, ctx: PanelContext) -> bool:
        """Whether this viewer may add any email address to the staff, not
        only the people they may pick."""
        return can(cast("User", ctx.request.user), ADD_STAFF_MEMBER, _organisation(ctx))

    def _adds_staff(self, ctx: PanelContext) -> bool:
        """Whether this viewer is offered "No roles yet"."""
        return self.offers_no_role and self._may_add_anyone(ctx)

    def is_offered(self, ctx: PanelContext) -> bool:
        return bool(self._grantable(ctx))

    def _grantable(self, ctx: PanelContext) -> list[GrantableRole]:
        return grantable_roles_for(ctx.request)

    def _preset(self, ctx: PanelContext) -> Cohort | None:
        return None

    def _dialog_title(self, ctx: PanelContext) -> str:
        preset = self._preset(ctx)
        return f"Add a staff member to {preset}" if preset else "Add a staff member"

    def _email_context(
        self, ctx: PanelContext, form: StaffEmailForm
    ) -> dict[str, object]:
        return {
            "step": "email",
            "dialog_title": self._dialog_title(ctx),
            "form": form,
            "field_error_count": field_error_count(form),
            "form_url": self.get_action_url(ctx),
            "search_url": self.get_action_url(ctx),
            "listbox_id": SEARCH_LISTBOX_ID,
            "searches_pickable_only": not self._may_add_anyone(ctx),
            "results": [],
            "needs_term": True,
            "term": "",
        }

    def _email_step(
        self, ctx: PanelContext, form: StaffEmailForm, status: int = 200
    ) -> HttpResponse:
        return render(
            ctx.request,
            self.template_name,
            self._email_context(ctx, form),
            status=status,
        )

    def _search_context(self, ctx: PanelContext) -> dict[str, object]:
        """The as-you-type matches for the typed term: up to
        ``SEARCH_RESULT_LIMIT`` of the people this viewer may pick."""
        term = ctx.request.GET["q"].strip()
        context: dict[str, object] = {
            "step": "search",
            "term": term,
            "listbox_id": SEARCH_LISTBOX_ID,
            "searches_pickable_only": not self._may_add_anyone(ctx),
            "needs_term": len(term) < MIN_TERM_LENGTH,
            "results": [],
            "truncated": False,
        }
        if context["needs_term"]:
            return context
        fetched = list(
            pickable_staff(cast("User", ctx.request.user), _organisation(ctx)).filter(
                term_condition(term, include_email=True)
            )[: self.SEARCH_RESULT_LIMIT + 1]
        )
        context["results"] = [
            {
                "pk": user.pk,
                "display_name": user.display_name,
                "email": user.email,
                "email_below_name": email_below_name(user),
            }
            for user in fetched[: self.SEARCH_RESULT_LIMIT]
        ]
        context["truncated"] = len(fetched) > self.SEARCH_RESULT_LIMIT
        return context

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        if "q" in ctx.request.GET:
            return self._search_context(ctx)
        return self._email_context(ctx, StaffEmailForm())

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        if not self._grantable(ctx):
            return denied_response(ctx, self)
        if ctx.request.POST.get("step") == "lookup":
            return self._lookup(ctx)
        return self._submit(ctx)

    def _other_site_response(self, ctx: PanelContext) -> HttpResponse:
        form = StaffEmailForm(ctx.request.POST)
        form.is_valid()
        form.add_error("email", OTHER_SITE_MESSAGE)
        return self._email_step(ctx, form, status=422)

    def _match(self, ctx: PanelContext, email: str) -> User | HttpResponse | None:
        """The account for `email`, None when there is none yet, or the
        response that says why the address cannot be used. Someone who may
        add staff looks up any address; anyone else matches only the people
        they may pick, with one message for every miss so the answer never
        reveals whether an account exists."""
        organisation = _organisation(ctx)
        actor = cast("User", ctx.request.user)
        if not self._may_add_anyone(ctx):
            user = (
                pickable_staff(actor, organisation).filter(email__iexact=email).first()
            )
            if user is None:
                return _refused(ctx, REFUSAL_MESSAGES[RefusalReason.NOT_VISIBLE])
            return user
        try:
            user = lookup_user(organisation.site, email)
        except EmailInUseOnAnotherSite:
            return self._other_site_response(ctx)
        return user

    def _fixed_person(self, ctx: PanelContext) -> User | None:
        """The staff member the page fixes, or None when the dialog looks the
        person up by address."""
        return None

    def _posted(self, ctx: PanelContext) -> QueryDict:
        """The submitted fields."""
        return ctx.request.POST

    @staticmethod
    def _unavailable_reason(grantable: GrantableRole, entries: list[RoleEntry]) -> str:
        """Why the role cannot be given again, or "" when it can: the person
        already holds it on the organisation or on every cohort offered."""
        held = next((e for e in entries if e.role == grantable.role), None)
        if held is None:
            return ""
        if grantable.cohorts is None:
            return "Already held"
        if grantable.cohorts and set(grantable.cohorts) <= set(held.cohorts):
            return "Already held on every cohort you can give"
        return ""

    def _role_cards(
        self, ctx: PanelContext, entries: list[RoleEntry]
    ) -> list[dict[str, str | bool]]:
        config = get_role_config(_organisation(ctx).site.name)
        return [
            {
                "key": grantable.role,
                "display_name": config[grantable.role].display_name,
                "description": config[grantable.role].description,
                "needs_cohorts": grantable.cohorts is not None,
                "unavailable_reason": self._unavailable_reason(grantable, entries),
            }
            for grantable in self._grantable(ctx)
        ]

    def _cohort_rows(
        self, ctx: PanelContext, chosen: list[str]
    ) -> list[dict[str, object]]:
        """One checklist row per cohort the grantor may give any cohort role
        on, each naming the roles it is offered for."""
        roles_by_cohort: dict[Cohort, list[str]] = {}
        for grantable in self._grantable(ctx):
            for cohort in grantable.cohorts or ():
                roles_by_cohort.setdefault(cohort, []).append(grantable.role)
        return [
            {
                "pk": str(cohort.pk),
                "name": cohort.name,
                "roles": " ".join(roles),
                "checked": str(cohort.pk) in chosen,
            }
            for cohort, roles in sorted(
                roles_by_cohort.items(), key=lambda item: item[0].name
            )
        ]

    def _role_note(self, ctx: PanelContext) -> str:
        if not Cohort.objects.filter(
            organisation=_organisation(ctx), is_active=True
        ).exists():
            return "This organisation has no active cohorts yet."
        offered = {grantable.role for grantable in self._grantable(ctx)}
        if any(role not in offered for role in self.offerable_roles):
            return "You can only give roles at or below your own."
        return ""

    def _role_step_context(
        self, ctx: PanelContext, user: User | None, form: AddStaffMemberForm
    ) -> dict[str, object]:
        chosen = [str(pk) for pk in form["cohorts"].value() or []]
        person = self._fixed_person(ctx)
        entries = (
            [] if person is None else current_role_entries(person, _organisation(ctx))
        )
        return {
            "step": "role",
            "dialog_title": self._dialog_title(ctx),
            "match": user,
            "new_account": user is None,
            "person": person,
            "current_entries": role_entries_shown_to(ctx.request, entries),
            "form": form,
            "field_error_count": field_error_count(form),
            "form_url": self.get_action_url(ctx),
            "role_cards": self._role_cards(ctx, entries),
            "preset_cohort": self._preset(ctx),
            "cohort_rows": self._cohort_rows(ctx, chosen),
            "selected_role": form["role"].value() or "",
            "offers_no_role": self._adds_staff(ctx),
            "role_note": self._role_note(ctx),
        }

    def _role_step(
        self,
        ctx: PanelContext,
        user: User | None,
        form: AddStaffMemberForm,
        status: int = 200,
    ) -> HttpResponse:
        return render(
            ctx.request,
            self.template_name,
            self._role_step_context(ctx, user, form),
            status=status,
        )

    def _lookup(self, ctx: PanelContext) -> HttpResponse:
        email_form = StaffEmailForm(ctx.request.POST)
        if not email_form.is_valid():
            return self._email_step(ctx, email_form, status=422)
        matched = self._match(ctx, email_form.cleaned_data["email"])
        if isinstance(matched, HttpResponse):
            return matched
        form = AddStaffMemberForm(
            None,
            roles=[
                (grantable.role, grantable.role) for grantable in self._grantable(ctx)
            ],
            cohorts=self._cohort_choices(ctx),
            preset=self._preset(ctx),
            new_account=matched is None,
            allow_no_role=self._adds_staff(ctx),
        )
        form.fields["email"].initial = email_form.cleaned_data["email"]
        return self._role_step(ctx, matched, form)

    def _cohort_choices(self, ctx: PanelContext) -> QuerySet[Cohort]:
        return Cohort.objects.filter(organisation=_organisation(ctx))

    def _targets(
        self, ctx: PanelContext, role: str, cohorts: list[Cohort]
    ) -> list[Organisation | Cohort] | None:
        """What the role is given on, or None when the grantor may not give
        this role there. The cohorts must be among that role's own grantable
        cohorts, not those of another role."""
        grantable = {g.role: g for g in self._grantable(ctx)}.get(role)
        if grantable is None:
            return None
        if grantable.cohorts is None:
            return [_organisation(ctx)]
        allowed = set(grantable.cohorts)
        if not all(cohort in allowed for cohort in cohorts):
            return None
        return list(cohorts)

    def _submit(self, ctx: PanelContext) -> HttpResponse:
        posted = self._posted(ctx)
        matched = self._match(ctx, posted.get("email", ""))
        if isinstance(matched, HttpResponse):
            return matched
        form = AddStaffMemberForm(
            posted,
            roles=[(role, role) for role in STAFF_ROLES],
            cohorts=self._cohort_choices(ctx),
            preset=self._preset(ctx),
            new_account=matched is None,
            allow_no_role=self._adds_staff(ctx),
        )
        if not form.is_valid():
            return self._role_step(ctx, matched, form, status=422)
        role = cast(str, form.cleaned_data["role"])
        cohorts = sorted(form.cleaned_data["cohorts"], key=lambda c: c.name)
        targets = [] if not role else self._targets(ctx, role, cohorts)
        if targets is None:
            return denied_response(ctx, self)
        email = cast(str, form.cleaned_data["email"])
        if not role:
            return self._submit_without_role(ctx, matched, email, form)
        before = (
            [] if matched is None else current_role_entries(matched, _organisation(ctx))
        )
        if role in ORGANISATION_ROLES and any(e.role == role for e in before):
            held_name = get_role_config(_organisation(ctx).site.name)[role].display_name
            return _refused(
                ctx,
                f"{_staff_member_name(matched, email)} is already {held_name} here.",
            )
        held = self._already_held(ctx, matched, role, cohorts)
        names = (
            (
                cast(str, form.cleaned_data["first_name"]),
                cast(str, form.cleaned_data["last_name"]),
            )
            if matched is None
            else ("", "")
        )
        new_cohorts = [cohort for cohort in cohorts if cohort not in held]
        if cohorts and not new_cohorts:
            return _refused(
                ctx,
                f"{_staff_member_name(matched, email)} already holds this role on "
                "these cohorts.",
            )
        new_targets: list[Organisation | Cohort] = [*new_cohorts] or targets
        if ctx.request.POST.get("confirmed") != "1":
            return self._confirmation(
                ctx, email, matched, role, new_cohorts, held, cohorts, names, before
            )
        return self._perform(ctx, matched, email, role, new_targets, names)

    def _submit_without_role(
        self,
        ctx: PanelContext,
        user: User | None,
        email: str,
        form: AddStaffMemberForm,
    ) -> HttpResponse:
        """Add `email` to the staff with no role: refused up front for
        someone already on the staff, so the person sees why before a
        confirm step. Someone who holds roles here with no StaffMember row
        is listed as inactive, and is refused as inactive: a new active row
        would switch those roles on without naming them."""
        organisation = _organisation(ctx)
        names = (
            (
                cast(str, form.cleaned_data["first_name"]),
                cast(str, form.cleaned_data["last_name"]),
            )
            if user is None
            else ("", "")
        )
        state = staff_member_state(user, organisation)
        existing = {
            "active": RefusalReason.ALREADY_STAFF,
            "inactive": RefusalReason.INACTIVE_STAFF_MEMBER,
        }.get(state)
        if (
            user is not None
            and state == "missing"
            and has_staff_assignments(user, organisation)
        ):
            existing = RefusalReason.INACTIVE_STAFF_MEMBER
        if existing is not None:
            return _refused(
                ctx,
                REFUSAL_MESSAGES[existing].format(name=_staff_member_name(user, email)),
            )
        if ctx.request.POST.get("confirmed") != "1":
            return render(
                ctx.request,
                self.template_name,
                {
                    "step": "confirmation",
                    "no_role": True,
                    "match": user,
                    "staff_member_name": _staff_member_name(user, email),
                    "creates_account": user is None,
                    "first_name": names[0],
                    "last_name": names[1],
                    "form_url": self.get_action_url(ctx),
                    "email": email,
                    "role": "",
                    "cohort_ids": [],
                },
            )
        return self._perform(ctx, user, email, "", [], names)

    def _already_held(
        self, ctx: PanelContext, user: User | None, role: str, cohorts: list[Cohort]
    ) -> list[Cohort]:
        """The cohorts among `cohorts` that `user` already holds `role` on."""
        if user is None or not cohorts:
            return []
        held_keys = set(
            staff_assignments(_organisation(ctx))
            .filter(user=user, role=role)
            .values_list("object_id", flat=True)
        )
        return [cohort for cohort in cohorts if str(cohort.pk) in held_keys]

    def _confirmation(
        self,
        ctx: PanelContext,
        email: str,
        user: User | None,
        role: str,
        cohorts: list[Cohort],
        already_held: list[Cohort],
        chosen: list[Cohort],
        names: tuple[str, str],
        before: list[RoleEntry],
    ) -> HttpResponse:
        organisation = _organisation(ctx)
        site = organisation.site
        role_config = get_role_config(site.name)[role]
        name = _staff_member_name(user, email)
        before = role_entries_shown_to(ctx.request, before)
        after = (
            _entries_after(
                before,
                cast("User", ctx.request.user),
                role,
                role_config.display_name,
                cohorts,
            )
            if before
            else []
        )
        return render(
            ctx.request,
            self.template_name,
            {
                "step": "confirmation",
                "match": user,
                "staff_member_name": name,
                "creates_account": user is None,
                "first_name": names[0],
                "last_name": names[1],
                "form_url": self.get_action_url(ctx),
                "person": self._fixed_person(ctx),
                "email": email,
                "role": role,
                "cohort_ids": [str(cohort.pk) for cohort in chosen],
                "already_held": join_prose([cohort.name for cohort in already_held]),
                "display_name": role_config.display_name,
                "description": role_config.description,
                "scope": (
                    ORGANISATION_SCOPE
                    if role in ORGANISATION_ROLES
                    else join_prose([cohort.name for cohort in cohorts])
                ),
                "current_entries": before,
                "after_entries": after,
                "staff_member_state": staff_member_state(user, organisation),
            },
        )

    def _perform(
        self,
        ctx: PanelContext,
        user: User | None,
        email: str,
        role: str,
        targets: list[Organisation | Cohort],
        names: tuple[str, str],
    ) -> HttpResponse:
        organisation = _organisation(ctx)
        name = _staff_member_name(user, email)
        try:
            with transaction.atomic():
                user, created = match_or_create_user(organisation.site, email, *names)
                if role:
                    for target in targets:
                        assign_role(cast("User", ctx.request.user), user, role, target)
                else:
                    add_staff_member(cast("User", ctx.request.user), user, organisation)
                if created:
                    send_account_setup_email(user, organisation.name)
        except RoleChangeRefused as refused:
            return role_refusal_response(ctx, self, refused, name)
        except EmailInUseOnAnotherSite:
            return self._other_site_response(ctx)
        return staff_member_changed_response(user, ctx)


class AddRoleAction(AddStaffMemberAction):
    """Gives one staff member another role, from their row. The person is
    fixed by the `user` parameter, so the dialog opens at the role step and
    the posted email is never read."""

    label = "Add role"
    action_name = "add_role"
    variant = "secondary"
    renders_in_footer = False
    offers_no_role = False

    def has_permission(self, ctx: PanelContext) -> bool:
        return has_grantable_roles(ctx)

    def _dialog_title(self, ctx: PanelContext) -> str:
        return f"Add a role for {_staff_member_param(ctx).display_name}"

    def _fixed_person(self, ctx: PanelContext) -> User | None:
        return _staff_member_param(ctx)

    def _posted(self, ctx: PanelContext) -> QueryDict:
        posted = ctx.request.POST.copy()
        posted["email"] = _staff_member_param(ctx).email
        return posted

    def _match(self, ctx: PanelContext, email: str) -> User:
        return _staff_member_param(ctx)

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        person = _staff_member_param(ctx)
        form = AddStaffMemberForm(
            None,
            roles=[(g.role, g.role) for g in self._grantable(ctx)],
            cohorts=self._cohort_choices(ctx),
        )
        form.fields["email"].initial = person.email
        return self._role_step_context(ctx, person, form)

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        if not self._grantable(ctx):
            return denied_response(ctx, self)
        return self._submit(ctx)


class AddStaffMemberToCohortAction(AddStaffMemberAction):
    """Add a staff member on a cohort's page, with the cohort fixed. Rendered by
    the Settings panel beside its Staff heading, not in the footer."""

    capability = ASSIGN_COHORT_VIEWER
    renders_in_footer = False
    offerable_roles = ("cohort_admin", "cohort_viewer")
    offers_no_role = False

    def permission_object(self, ctx: PanelContext) -> Model | None:
        return ctx.instance

    def is_offered(self, ctx: PanelContext) -> bool:
        # Someone who may add anyone needs nobody to pick from: they can type
        # an email address.
        return super().is_offered(ctx) and (
            self._may_add_anyone(ctx)
            or pickable_staff(
                cast("User", ctx.request.user), _organisation(ctx)
            ).exists()
        )

    def _grantable(self, ctx: PanelContext) -> list[GrantableRole]:
        cohort = cast(Cohort, ctx.instance)
        return [
            grantable
            for grantable in grantable_roles_for(ctx.request)
            if grantable.cohorts is not None and cohort in grantable.cohorts
        ]

    def _preset(self, ctx: PanelContext) -> Cohort | None:
        return cast(Cohort, ctx.instance)


class CohortRoleAction(ModalPanelAction):
    """An action on one person's one cohort role on this cohort, named by the
    `user` and `role` parameters. The assignment is re-read on every request;
    one that is gone or inactive is a 404 that the action route answers with
    its unavailable fragment."""

    variant = "secondary"
    renders_in_footer = False

    def permission_object(self, ctx: PanelContext) -> Model | None:
        return ctx.instance

    def has_permission(self, ctx: PanelContext) -> bool:
        return ctx.instance is not None and bool(self._grantable(ctx))

    def _grantable(self, ctx: PanelContext) -> set[str]:
        return roles_grantable_on(ctx.request, cast(Cohort, ctx.instance))

    def _assignment(self, ctx: PanelContext) -> ObjectRoleAssignment:
        cohort = cast(Cohort, ctx.instance)
        user = _staff_member_param(ctx)
        role = _action_params(ctx.request).get("role", "")
        if role_target(role) != "cohort" or role not in STAFF_ROLES:
            raise Http404("Not a cohort role")
        return get_object_or_404(
            _active_role_assignments(Cohort, frozenset({role})).select_related("user"),
            user=user,
            object_id=str(cohort.pk),
        )


class ChangeRoleAction(CohortRoleAction):
    """Swaps one cohort role of a staff member on this cohort for another,
    after a confirm step. Both roles are checked before anything is written,
    so a refusal leaves the original role active."""

    label = "Change role"
    action_name = "change_role"
    template_name = "educator_interface/modal/change_role.html"

    def _cohort_roles(self, ctx: PanelContext) -> list[str]:
        """The cohort roles among the staff roles, in display order."""
        return [role for role in STAFF_ROLES if role_target(role) == "cohort"]

    def _role_cards(self, ctx: PanelContext, held: str) -> list[dict[str, object]]:
        config = get_role_config(cast(Cohort, ctx.instance).site.name)
        grantable = self._grantable(ctx)
        return [
            {
                "value": role,
                "display_name": config[role].display_name,
                "description": config[role].description,
                "checked": role == held,
            }
            for role in self._cohort_roles(ctx)
            if role in grantable
        ]

    def _form(
        self, ctx: PanelContext, data: Mapping[str, str] | None
    ) -> ChangeRoleForm:
        config = get_role_config(cast(Cohort, ctx.instance).site.name)
        return ChangeRoleForm(
            data,
            roles=[
                (role, config[role].display_name) for role in self._cohort_roles(ctx)
            ],
        )

    def _dialog_context(
        self, ctx: PanelContext, assignment: ObjectRoleAssignment
    ) -> dict[str, object]:
        context = super().get_context_data(ctx)
        context.update(
            {
                "step": "form",
                "staff_member": assignment.user,
                "role": assignment.role,
                "cohort": ctx.instance,
                "role_cards": self._role_cards(ctx, assignment.role),
                "form_url": self.get_action_url(ctx),
            }
        )
        return context

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        return self._dialog_context(ctx, self._assignment(ctx))

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        assignment = self._assignment(ctx)
        cohort = cast(Cohort, ctx.instance)
        user = assignment.user
        form = self._form(ctx, ctx.request.POST)
        if not form.is_valid():
            return render(
                ctx.request,
                self.template_name,
                {**self._dialog_context(ctx, assignment), "form": form},
                status=422,
            )
        new_role = str(form.cleaned_data["new_role"])
        config = get_role_config(cohort.site.name)
        if new_role == assignment.role:
            return _refused(
                ctx,
                f"{user.display_name} already holds "
                f"{config[new_role].display_name} on {cohort}.",
            )
        grantable = self._grantable(ctx)
        if assignment.role not in grantable or new_role not in grantable:
            return denied_response(ctx, self)
        if ctx.request.POST.get("confirmed") != "1":
            return render(
                ctx.request,
                self.template_name,
                {
                    **self._dialog_context(ctx, assignment),
                    "step": "confirmation",
                    "new_role": new_role,
                    "new_role_display_name": config[new_role].display_name,
                },
            )
        grantor = cast("User", ctx.request.user)
        try:
            # The new role first: a grantor changing their own role still
            # holds the old one while the new one is checked.
            with transaction.atomic():
                assign_role(grantor, user, new_role, cohort)
                deactivate_role(grantor, user, assignment.role, cohort)
        except RoleChangeRefused as refused:
            return role_refusal_response(ctx, self, refused, user.display_name)
        return staff_member_changed_response(user, ctx)


class RemoveStaffFromCohortAction(EducatorReasonMixin, CohortRoleAction):
    """Takes one cohort role off a staff member on this cohort alone."""

    label = "Remove from cohort"
    action_name = "remove_staff_from_cohort"
    template_name = (
        "educator_interface/modal/remove_staff_from_cohort_confirmation.html"
    )

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        assignment = self._assignment(ctx)
        cohort = cast(Cohort, ctx.instance)
        context = super().get_context_data(ctx)
        context.update(
            {
                "staff_member": assignment.user,
                "role": assignment.role,
                "role_display_name": get_role_config(cohort.site.name)[
                    assignment.role
                ].display_name,
                "cohort": cohort,
                "confirm_url": self.get_action_url(ctx),
            }
        )
        return context

    def handle_confirmed_submit(self, ctx: PanelContext) -> HttpResponse:
        assignment = self._assignment(ctx)
        if assignment.role not in self._grantable(ctx):
            return denied_response(ctx, self)
        user = assignment.user
        try:
            with transaction.atomic():
                deactivate_role(
                    cast("User", ctx.request.user),
                    user,
                    assignment.role,
                    cast(Cohort, ctx.instance),
                    reason=ctx.reason,
                )
        except RoleChangeRefused as refused:
            return role_refusal_response(ctx, self, refused, user.display_name)
        return staff_member_changed_response(user, ctx)


class StaffRoleAction(ModalPanelAction):
    """An action on one role entry of one staff member, named by the `user` and
    `role` parameters. Renders per entry, never in the header. The target
    is re-read on every request through staff_of, so a staff member who has
    since lost every role, or a role no longer held, is a 404 that the
    action route answers with its unavailable fragment."""

    variant = "secondary"
    renders_in_footer = False

    def has_permission(self, ctx: PanelContext) -> bool:
        return has_grantable_roles(ctx)

    def get_capability(self, ctx: PanelContext) -> str | None:
        role = _action_params(ctx.request).get("role", "")
        if role in STAFF_ROLES:
            return ASSIGN.format(role=role)
        return ASSIGN.format(role="cohort_viewer")

    def permission_object(self, ctx: PanelContext) -> Model | None:
        return _organisation(ctx)

    def _entries(self, ctx: PanelContext, user: User) -> list[RoleEntry]:
        """Every role `user` holds here, loaded once per request."""
        return current_role_entries(user, _organisation(ctx))

    def _reach(self, ctx: PanelContext, role: str) -> set[Cohort]:
        return role_reach(ctx.request, role)

    def _entry(self, ctx: PanelContext, entries: list[RoleEntry]) -> RoleEntry:
        """The entry the `role` parameter names, from `entries`."""
        role = _action_params(ctx.request).get("role", "")
        for entry in entries:
            if entry.role == role:
                return entry
        raise Http404("The staff member does not hold this role")

    def _readable(self, ctx: PanelContext, entry: RoleEntry) -> list[Cohort]:
        """The entry's cohorts the viewer may read: all of them for someone
        who may see staff roles, else the ones within their reach, which
        that cohort's own Staff list already shows them."""
        if may_see_staff_roles(ctx.request):
            return list(entry.cohorts)
        reach = self._reach(ctx, entry.role)
        return [cohort for cohort in entry.cohorts if cohort in reach]


class DeactivateRoleAction(EducatorReasonMixin, ConfirmAction, StaffRoleAction):
    """Takes one role entry off a staff member: on the organisation, or on every
    cohort of the entry the grantor can act on. A cohort outside the
    grantor's reach keeps the role, and the dialog says so. An entry with no
    cohort in reach has no trigger, and is a 404 dialog and a 403 submit."""

    label = "Deactivate role"
    action_name = "deactivate_role"
    confirm_label = "Deactivate"
    loading_text = "Deactivating…"
    template_name = "educator_interface/modal/deactivate_role_confirmation.html"

    def _split(
        self, ctx: PanelContext, entry: RoleEntry
    ) -> tuple[list[Cohort], list[Cohort]]:
        """The entry's cohorts the grantor may act on, then the ones that stay."""
        reach = self._reach(ctx, entry.role)
        return (
            [cohort for cohort in entry.cohorts if cohort in reach],
            [cohort for cohort in entry.cohorts if cohort not in reach],
        )

    def _kept(
        self,
        ctx: PanelContext,
        user: User,
        removed: RoleEntry,
        entries: list[RoleEntry],
        possessive: str,
    ) -> str:
        """What the person keeps, in prose; `possessive` is "their", or "your"
        when the viewer is removing their own role."""
        organisation = _organisation(ctx)
        kept = [
            f"{entry.display_name} on {entry.scope}"
            for entry in entries
            if entry.role != removed.role
        ]
        has_learner = Learner.objects.filter(
            organisation=organisation, user=user, is_active=True
        ).exists()
        parts = [f"{possessive} account", *kept]
        if has_learner:
            parts.append(f"{possessive} learner access in this organisation")
        return join_prose(parts)

    def get_hidden_fields(self, ctx: PanelContext) -> dict[str, str]:
        params = _action_params(ctx.request)
        return {"user": params.get("user", ""), "role": params.get("role", "")}

    def get_confirm_context(self, ctx: PanelContext) -> dict[str, object]:
        organisation = _organisation(ctx)
        site = organisation.site
        grantor = cast("User", ctx.request.user)
        user = _staff_member_param(ctx)
        entries = self._entries(ctx, user)
        entry = self._entry(ctx, entries)
        # A role the viewer cannot act on answers as one the person does not
        # hold, so the response never confirms who holds it.
        if entry.role not in actionable_roles(ctx.request, [entry]):
            raise Http404("This role is not the grantor's to deactivate")
        removed, staying = self._split(ctx, entry)
        shows_roles = may_see_staff_roles(ctx.request)
        is_self = user.pk == grantor.pk
        shown_entries = role_entries_shown_to(ctx.request, entries)
        description = get_role_config(site.name)[entry.role].description.rstrip(".")
        return {
            "staff_member": user,
            "entry": entry,
            "description": description,
            "full_scope": (
                "the whole organisation"
                if entry.target == "organisation"
                else join_prose([cohort.name for cohort in removed])
            ),
            "stays": (
                join_prose([cohort.name for cohort in staying]) if shows_roles else ""
            ),
            "keeps": self._kept(
                ctx, user, entry, shown_entries, "your" if is_self else "their"
            ),
            "is_self": is_self,
            # Nothing else left here: the person stays on the staff list
            # with no roles, which a site-level admin's dialog says.
            "last_role": not staying
            and all(other.role == entry.role for other in shown_entries),
            "last_organisation_admin": entry.role == "organisation_admin"
            and is_last_organisation_admin(organisation, user),
            "grantor_is_site_level": is_site_level_admin(grantor, site),
            "target_is_site_level": shows_roles and is_site_level_admin(user, site),
        }

    def handle_confirmed_submit(self, ctx: PanelContext) -> HttpResponse:
        organisation = _organisation(ctx)
        user = _staff_member_param(ctx)
        entry = self._entry(ctx, self._entries(ctx, user))
        removed, _ = self._split(ctx, entry)
        targets: list[Organisation | Cohort] = (
            [organisation] if entry.target == "organisation" else [*removed]
        )
        if not targets:
            return denied_response(ctx, self)
        try:
            with transaction.atomic():
                for target in targets:
                    deactivate_role(
                        cast("User", ctx.request.user),
                        user,
                        entry.role,
                        target,
                        reason=ctx.reason,
                    )
        except RoleChangeRefused as refused:
            return role_refusal_response(ctx, self, refused, user.display_name)
        return staff_member_changed_response(user, ctx)


class CohortChange(NamedTuple):
    added: list[Cohort]
    removed: list[Cohort]
    untouched: list[Cohort]


class ChangeCohortsAction(StaffRoleAction):
    """Adds and removes the cohorts of one cohort-role entry in a single
    transaction, after a confirmation that names what is gained and lost. An
    entry with no cohort in the grantor's reach has no trigger and is a 404:
    giving that role on another cohort is Add role's job."""

    label = "Change cohorts"
    action_name = "change_cohorts"
    template_name = "educator_interface/modal/change_cohorts.html"

    def is_offered(self, ctx: PanelContext) -> bool:
        return any(g.cohorts for g in grantable_roles_for(ctx.request))

    def _offered(self, ctx: PanelContext, role: str) -> tuple[Cohort, ...]:
        for grantable in grantable_roles_for(ctx.request):
            if grantable.role == role and grantable.cohorts is not None:
                return grantable.cohorts
        raise Http404("This role is not given on cohorts here")

    def _entry(self, ctx: PanelContext, entries: list[RoleEntry]) -> RoleEntry:
        entry = super()._entry(ctx, entries)
        reach = self._reach(ctx, entry.role)
        if not any(cohort in reach for cohort in entry.cohorts):
            raise Http404("No cohort of this role is within the grantor's reach")
        return entry

    def _plan(
        self, ctx: PanelContext, entry: RoleEntry, chosen: list[Cohort]
    ) -> CohortChange:
        """Cohorts the person holds outside the offered set, and inactive
        ones they hold, are untouched."""
        offered = self._offered(ctx, entry.role)
        held = list(entry.cohorts)
        return CohortChange(
            added=[cohort for cohort in chosen if cohort not in held],
            removed=[
                cohort for cohort in held if cohort in offered and cohort not in chosen
            ],
            untouched=[cohort for cohort in held if cohort not in offered],
        )

    def _dialog(
        self, ctx: PanelContext, user: User, entry: RoleEntry
    ) -> dict[str, object]:
        offered = self._offered(ctx, entry.role)
        held = set(entry.cohorts)
        return {
            "staff_member": user,
            "entry": entry,
            "form_url": self.get_action_url(ctx),
            "cohort_rows": [
                {
                    "pk": str(cohort.pk),
                    "name": cohort.name,
                    "checked": cohort in held,
                }
                for cohort in offered
            ],
            "read_only": [
                f"{cohort.name} (inactive)"
                if not cohort.is_active
                else f"{cohort.name} (outside the cohorts you can give)"
                for cohort in self._readable(ctx, entry)
                if cohort not in offered
            ],
        }

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        user = _staff_member_param(ctx)
        entry = self._entry(ctx, self._entries(ctx, user))
        return {"step": "form", **self._dialog(ctx, user, entry)}

    def _chosen(self, ctx: PanelContext, entry: RoleEntry) -> list[Cohort]:
        form = CohortSetForm(ctx.request.POST)
        cohorts = cast(forms.ModelMultipleChoiceField, form.fields["cohorts"])
        cohorts.queryset = Cohort.objects.filter(organisation=_organisation(ctx))
        if not form.is_valid():
            raise Http404("No such cohort")
        chosen = sorted(form.cleaned_data["cohorts"], key=lambda c: c.name)
        offered = self._offered(ctx, entry.role)
        if not all(cohort in offered for cohort in chosen):
            raise Http404("This cohort is no longer offered")
        return chosen

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        user = _staff_member_param(ctx)
        grantor = cast("User", ctx.request.user)
        entry = self._entry(ctx, self._entries(ctx, user))
        chosen = self._chosen(ctx, entry)
        plan = self._plan(ctx, entry, chosen)
        if not plan.added and not plan.removed:
            return _refused(ctx, "Nothing changed. Tick or untick a cohort first.")
        if ctx.request.POST.get("confirmed") != "1":
            return self._confirmation(ctx, user, entry, chosen, plan)
        try:
            with transaction.atomic():
                for cohort in plan.added:
                    assign_role(grantor, user, entry.role, cohort)
                for cohort in plan.removed:
                    deactivate_role(grantor, user, entry.role, cohort)
        except RoleChangeRefused as refused:
            return role_refusal_response(ctx, self, refused, user.display_name)
        return staff_member_changed_response(user, ctx)

    def _confirmation(
        self,
        ctx: PanelContext,
        user: User,
        entry: RoleEntry,
        chosen: list[Cohort],
        plan: CohortChange,
    ) -> HttpResponse:
        organisation = _organisation(ctx)
        return render(
            ctx.request,
            self.template_name,
            {
                "step": "confirmation",
                "staff_member": user,
                "entry": entry,
                "form_url": self.get_action_url(ctx),
                "cohort_ids": [str(cohort.pk) for cohort in chosen],
                "added": join_prose([cohort.name for cohort in plan.added]),
                "removed": join_prose([cohort.name for cohort in plan.removed]),
                "removes_role": not plan.added
                and len(plan.removed) == len(self._readable(ctx, entry)),
                "staff_member_state": staff_member_state(user, organisation),
            },
        )


class StaffMemberStateAction(ConfirmAction):
    """Flips one staff member's StaffMember row, named by the `user`
    parameter, after confirmation. Renders per row, never in the header."""

    renders_in_footer = False
    capability = CHANGE_STAFF_MEMBER

    def get_hidden_fields(self, ctx: PanelContext) -> dict[str, str]:
        return {"user": _action_params(ctx.request).get("user", "")}

    def permission_object(self, ctx: PanelContext) -> Model | None:
        return _organisation(ctx)

    def _row(self, user: User, organisation: Organisation) -> StaffMember | None:
        return StaffMember.objects.filter(user=user, organisation=organisation).first()


class DeactivateStaffMemberAction(EducatorReasonMixin, StaffMemberStateAction):
    label = "Deactivate staff member"
    action_name = "deactivate"
    confirm_label = "Deactivate"
    loading_text = "Deactivating…"
    template_name = "educator_interface/modal/deactivate_staff_member_confirmation.html"

    def get_confirm_context(self, ctx: PanelContext) -> dict[str, object]:
        organisation = _organisation(ctx)
        user = _staff_member_param(ctx)
        return {
            "staff_member": user,
            "organisation": organisation,
            "last_organisation_admin": is_last_organisation_admin(organisation, user),
            "grantor_is_site_level": is_site_level_admin(
                cast("User", ctx.request.user), organisation.site
            ),
        }

    def handle_confirmed_submit(self, ctx: PanelContext) -> HttpResponse:
        organisation = _organisation(ctx)
        user = _staff_member_param(ctx)
        row = self._row(user, organisation)
        if row is None or not row.is_active:
            raise Http404("The staff member is already inactive")
        try:
            set_staff_member_active(
                cast("User", ctx.request.user),
                row,
                False,
                reason=ctx.reason,
            )
        except RoleChangeRefused as refused:
            return role_refusal_response(ctx, self, refused, user.display_name)
        return staff_member_changed_response(user, ctx)


class ReactivateStaffMemberAction(StaffMemberStateAction):
    label = "Reactivate staff member"
    action_name = "reactivate"
    confirm_label = "Reactivate"
    loading_text = "Reactivating…"
    template_name = "educator_interface/modal/reactivate_staff_member_confirmation.html"

    def get_confirm_context(self, ctx: PanelContext) -> dict[str, object]:
        user = _staff_member_param(ctx)
        entries = current_role_entries(user, _organisation(ctx))
        return {
            "staff_member": user,
            "roles": join_prose(
                [f"{entry.display_name} on {entry.scope}" for entry in entries]
            ),
        }

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        organisation = _organisation(ctx)
        user = _staff_member_param(ctx)
        row = self._row(user, organisation)
        if row is not None and row.is_active:
            raise Http404("The staff member is already active")
        try:
            with transaction.atomic():
                # A staff member with no row has no access, so the row is created
                # inactive and reactivated below rather than created active:
                # set_staff_member_active is the one path that checks
                # the actor's capability, locks the row and writes the entry,
                # and it only writes for a real change.
                row = row or ensure_staff_member(user, organisation, is_active=False)
                set_staff_member_active(cast("User", ctx.request.user), row, True)
        except RoleChangeRefused as refused:
            return role_refusal_response(ctx, self, refused, user.display_name)
        return staff_member_changed_response(user, ctx)


BULK_ACTIONS: dict[tuple[str, str], type[EducatorBulkAction]] = {}


def register_bulk_action[ActionT: type[EducatorBulkAction]](cls: ActionT) -> ActionT:
    """Class decorator: file the action under its table and name, in
    registration order, which is the order the action bar lists them."""
    BULK_ACTIONS[(cls.table_key, cls.action_name)] = cls
    return cls


def bulk_actions_for_table(table_key: str) -> list[EducatorBulkAction]:
    return [
        action_class()
        for (key, _name), action_class in BULK_ACTIONS.items()
        if key == table_key
    ]


class EducatorBulkAction(RecordedBulkAction):
    """A bulk action over the rows of an educator-interface table, scoped to
    the organisation the request was made under.

    Each object is changed with the same capability and service its
    single-object action uses. `permitted` decides which objects the user may
    change; it is read once per preview and once per run, so the preview and
    the run agree and the cost does not grow with the selection. Subclasses
    fill in the hooks; the defaults suit an action with no target picker.
    """

    capability: str
    #: The skip reason when the service reports nothing changed.
    unchanged_reason: str = ""
    #: The pks `permitted` returned, set by `prepare`.
    permitted_ids: frozenset[object] = frozenset()

    def has_permission(self, request: HttpRequest) -> bool:
        scoped = cast("OrganisationScopedRequest", request)
        return can_on_any(scoped.user, scoped.organisation, self.capability)

    def permitted(
        self,
        user: AbstractBaseUser | AnonymousUser,
        organisation: Organisation,
        queryset: QuerySet,
        cleaned_data: dict[str, object],
    ) -> QuerySet:
        """`queryset` narrowed to the objects the user may act on."""
        raise NotImplementedError

    def skip_reason(self, obj: Model, cleaned_data: dict[str, object]) -> str | None:
        """The reason this permitted object would be skipped, from its
        current state; None when it would change."""
        return None

    def prepare(
        self,
        user: AbstractBaseUser | AnonymousUser,
        scope: Model | None,
        queryset: QuerySet,
        cleaned_data: dict[str, object],
    ) -> None:
        self.permitted_ids = frozenset(
            self.permitted(
                user, cast(Organisation, scope), queryset, cleaned_data
            ).values_list("pk", flat=True)
        )

    def perform(self, obj: Model, cleaned_data: dict[str, object], actor: User) -> bool:
        """Call the service; False when it reports nothing changed."""
        raise NotImplementedError

    def objects_for_keys(self, scope: Model | None, keys: list[str]) -> QuerySet:
        # Narrowed to the run's organisation, so a key from another one can
        # never be reached through a stored run.
        return self.noun_model._base_manager.filter(
            organisation=cast(Organisation, scope), pk__in=keys
        )

    def on_finished(self, run: BulkActionRun) -> None:
        raise_notification(
            user=run.requested_by,
            category="bulk_action.finished",
            target=run,
            site_id=run.site_id,
            data={"summary": run_summary(run)},
        )

    def on_result_shown(self, request: HttpRequest, run: BulkActionRun) -> None:
        mark_notifications_read(
            user=cast("User", request.user), target=run, site_id=run.site_id
        )

    def not_permitted_reason(self) -> str:
        return (
            f"{self.noun_model._meta.verbose_name_plural} "
            "you don't have permission to change"
        )

    def classify_all(
        self,
        request: HttpRequest,
        queryset: QuerySet,
        cleaned_data: dict[str, object],
    ) -> dict[str, BulkOutcome] | None:
        scoped = cast("OrganisationScopedRequest", request)
        self.prepare(scoped.user, scoped.organisation, queryset, cleaned_data)
        outcomes: dict[str, BulkOutcome] = {}
        for obj in self.with_related(queryset):
            if obj.pk not in self.permitted_ids:
                outcomes[str(obj.pk)] = BulkOutcome(
                    "skipped", self.not_permitted_reason()
                )
            elif (reason := self.skip_reason(obj, cleaned_data)) is not None:
                outcomes[str(obj.pk)] = BulkOutcome("skipped", reason)
            else:
                outcomes[str(obj.pk)] = BulkOutcome("changed")
        return outcomes

    def changed_count(self, classified: dict[str, BulkOutcome] | None) -> int:
        counts = count_outcomes(classified or {})
        return sum(item.count for item in counts if item.status == "changed")

    def changed_keys(self, classified: dict[str, BulkOutcome] | None) -> list[str]:
        return [
            key
            for key, outcome in (classified or {}).items()
            if outcome.status == "changed"
        ]

    def sentence(self, count: int, cleaned_data: dict[str, object]) -> str:
        """The confirmation sentence for the `count` objects that will change."""
        raise NotImplementedError

    def confirmation_title(self, count: int, cleaned_data: dict[str, object]) -> str:
        """The sentence, asked: every dialog's heading is its sentence with
        a question mark, so wording lives in one place."""
        return self.sentence(count, cleaned_data).removesuffix(".") + "?"

    def consequences(
        self,
        queryset: QuerySet,
        classified: dict[str, BulkOutcome] | None,
        cleaned_data: dict[str, object],
    ) -> list[str]:
        """What the change means beyond itself, one line each. None by default."""
        return []

    def confirmation_wording(
        self,
        request: HttpRequest,
        queryset: QuerySet,
        classified: dict[str, BulkOutcome] | None,
        cleaned_data: dict[str, object],
    ) -> ConfirmationWording:
        wording = super().confirmation_wording(
            request, queryset, classified, cleaned_data
        )
        return ConfirmationWording(
            sentence=self.sentence(self.changed_count(classified), cleaned_data),
            skips=wording.skips,
            consequences=self.consequences(queryset, classified, cleaned_data),
        )

    def apply(
        self,
        user: AbstractBaseUser | AnonymousUser,
        obj: Model,
        cleaned_data: dict[str, object],
    ) -> BulkOutcome:
        if obj.pk not in self.permitted_ids:
            return BulkOutcome("skipped", self.not_permitted_reason())
        if self.perform(obj, cleaned_data, cast("User", user)):
            return BulkOutcome("changed")
        # The service said nothing changed, so the reason the preview gave
        # applies here too.
        return BulkOutcome("skipped", self.unchanged_reason)


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
        organisation: Organisation,
        queryset: QuerySet,
        cleaned_data: dict[str, object],
    ) -> QuerySet:
        return queryset.filter(
            pk__in=learners_permitted_for(user, organisation, self.capability).values(
                "pk"
            )
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
        organisation: Organisation,
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
        lost = courses_lost_by_any(
            queryset.filter(pk__in=self.changed_keys(classified)),
            cast(Cohort, cleaned_data["cohort"]),
        )
        if not lost:
            return []
        return [
            f"They lose access to: {join_prose([course.title for course in lost])}."
        ]


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


class CoursePickerMixin(RecordedBulkAction):
    """The course picker the course registration actions share: its form,
    and the picked course as a run stores it and reads it back. Declared on
    RecordedBulkAction so the overrides type-check; list it before the
    action in the bases."""

    form_class = BulkTargetPickerForm

    def get_form(self, request: HttpRequest, data: QueryDict | None) -> forms.Form:
        return BulkTargetPickerForm(
            data,
            field_name="course",
            queryset=registerable_courses(
                cast("OrganisationScopedRequest", request).organisation
            ),
            label="Course",
        )

    def target_json(self, cleaned_data: dict[str, object]) -> dict[str, str]:
        return {"course": str(cast(Course, cleaned_data["course"]).pk)}

    def resolve_target(
        self, scope: Model | None, target: dict[str, str]
    ) -> dict[str, object]:
        return {
            "course": get_object_or_404(
                registerable_courses(cast(Organisation, scope)),
                pk=target["course"],
            )
        }


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
        course = cast(Course, cleaned_data["course"])
        return f"Register {count_noun(Learner, count)} for {course.title}."


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
        course = cast(Course, cleaned_data["course"])
        return f"Deactivate the {course.title} registration for {count_noun(Learner, count)}."

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

    def confirmation_wording(
        self,
        request: HttpRequest,
        queryset: QuerySet,
        classified: dict[str, BulkOutcome] | None,
        cleaned_data: dict[str, object],
    ) -> ConfirmationWording:
        wording = super().confirmation_wording(
            request, queryset, classified, cleaned_data
        )
        # "account already set up" names its own subject, so it cannot follow
        # the "N is/are" the skip lines put in front of a reason; result_line
        # words both of this action's reasons for the same cause.
        set_up = sum(
            skip.count for skip in wording.skips if skip.reason == self.unchanged_reason
        )
        return ConfirmationWording(
            sentence=wording.sentence,
            skips=[
                skip for skip in wording.skips if skip.reason != self.unchanged_reason
            ],
            consequences=(
                [
                    f"{count_noun(Learner, set_up)} "
                    f"{'is' if set_up == 1 else 'are'} "
                    "already set up and will be skipped."
                ]
                if set_up
                else []
            ),
        )


class CohortBulkAction(EducatorBulkAction):
    """A bulk action over the rows of the cohorts table."""

    table_key = "cohorts"
    noun_model = Cohort

    def with_related(self, queryset: QuerySet) -> QuerySet:
        return queryset.select_related("organisation", "site")

    def permitted(
        self,
        user: AbstractBaseUser | AnonymousUser,
        organisation: Organisation,
        queryset: QuerySet,
        cleaned_data: dict[str, object],
    ) -> QuerySet:
        return queryset.filter(
            pk__in=cohorts_visible_to(
                user, organisation, capability=self.capability
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
        course = cast(Course, cleaned_data["course"])
        return f"Register {count_noun(Cohort, count)} for {course.title}."


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
        course = cast(Course, cleaned_data["course"])
        return f"Deactivate the {course.title} registration for {count_noun(Cohort, count)}."

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
