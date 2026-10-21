"""Panel actions on a cohort that need more than the generic framework ones."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, NamedTuple, cast
from uuid import UUID

from django import forms
from django.db import transaction
from django.db.models import Model, QuerySet
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.utils import timezone

from freedom_ls.accounts.account_setup import (
    AccountAlreadySetUp,
    EmailInUseOnAnotherSite,
    SetupEmailRecentlySent,
    is_pending,
    lookup_user,
    match_or_create_user,
    resend_account_setup_email,
    send_account_setup_email,
)
from freedom_ls.accounts.config import config as accounts_config
from freedom_ls.educator_interface.events import (
    COHORT_CHANGED,
    LEARNER_CHANGED,
    MEMBER_CHANGED,
    REGISTRATION_CHANGED,
)
from freedom_ls.educator_interface.forms import (
    AddLearnersForm,
    AddMemberForm,
    CohortCourseRegistrationForm,
    CohortPickerForm,
    CohortSetForm,
    LearnerCourseRegistrationForm,
    LearnerNameForm,
    LearnerPickerForm,
    MemberEmailForm,
)
from freedom_ls.educator_interface.members import (
    ORGANISATION_SCOPE,
    RoleEntry,
    current_role_entries,
)
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.learner_actions import (
    add_learners,
    add_to_cohort,
    deactivate_learner,
    move_between_cohorts,
    reactivate_learner,
    register_for_course,
    remove_from_cohort,
    unregister_from_course,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
    OrganisationMember,
)
from freedom_ls.learner_management.queries import (
    ADD_COHORTMEMBERSHIP,
    MEMBER_ROLES,
    cohort_course_count,
    cohort_is_empty,
    cohort_learner_count,
    cohorts_visible_to,
    courses_gaining_access,
    courses_losing_access,
    learners_visible_to,
    member_assignments,
    members_keeping_access,
    members_of,
    other_grants_for,
)
from freedom_ls.learner_management.role_assignment import (
    ASSIGN,
    CHANGE_MEMBER,
    GrantableRole,
    assign_role,
    grantable_roles,
    is_last_organisation_admin,
    is_site_level_admin,
    is_widening,
    remove_role,
    set_organisation_member_active,
)
from freedom_ls.learner_management.utils import (
    ensure_organisation_member,
    register_cohort_for_course,
    unregister_cohort_from_course,
)
from freedom_ls.learner_progress.utils import move_progress_preview
from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.panel_framework.actions import (
    DeleteAction,
    EditAction,
    FormPanelAction,
    PanelAction,
    changed_response,
    count_noun,
    count_phrase,
    denied_response,
    form_fragment_context,
    join_prose,
    navigation_response,
)
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.events import build_hx_trigger
from freedom_ls.role_based_permissions.exceptions import (
    RefusalReason,
    RoleChangeRefused,
)
from freedom_ls.role_based_permissions.loader import get_role_config

if TYPE_CHECKING:
    from freedom_ls.accounts.models import User
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


def _member_param(ctx: PanelContext) -> User:
    """The organisation member named by the action's `user` parameter. A
    missing, malformed or non-member value is a 404."""
    try:
        pk = int(_action_params(ctx.request).get("user", ""))
    except ValueError:
        raise Http404("No such user") from None
    return get_object_or_404(members_of(_organisation(ctx)), pk=pk)


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


class ResendSetupEmailAction(PanelAction):
    """Sends a pending learner the account setup email again, after confirmation."""

    label = "Resend setup email"
    action_name = "resend_setup_email"
    trigger_template_name = "panel_framework/partials/modal_trigger.html"
    variant = "secondary"
    capability = "freedom_ls_learner_management.change_learner"
    template_name = "educator_interface/modal/resend_setup_email_confirmation.html"

    def is_offered(self, ctx: PanelContext) -> bool:
        return is_pending(cast(Learner, ctx.instance).user)

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        context = super().get_context_data(ctx)
        context["learner"] = ctx.instance
        return context

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        learner = cast(Learner, ctx.instance)
        try:
            resend_account_setup_email(learner.user, learner.organisation.name)
        except SetupEmailRecentlySent:
            return render(
                ctx.request,
                "educator_interface/modal/setup_email_recently_sent.html",
                {
                    "learner": learner,
                    "minutes": accounts_config.SETUP_EMAIL_RESEND_SECONDS // 60,
                },
                status=422,
            )
        except AccountAlreadySetUp:
            return render(
                ctx.request,
                "educator_interface/modal/account_already_set_up.html",
                {"learner": learner},
                status=422,
            )
        return changed_response({LEARNER_CHANGED: [str(learner.pk)]})


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


def _registration_changed_response(learner: Learner) -> HttpResponse:
    ids = [str(learner.pk)]
    return changed_response({REGISTRATION_CHANGED: ids, LEARNER_CHANGED: ids})


class RegisterLearnerForCourseAction(FormPanelAction):
    """Registers the learner on the page for a course they hold no active
    individual registration for."""

    label = "Register for course"
    action_name = "register_for_course"
    capability = "freedom_ls_learner_management.add_learnercourseregistration"
    submit_buttons = [
        {"label": "Register", "variant": "primary", "loading_text": "Registering..."}
    ]
    _learner: Learner

    def _bind(self, ctx: PanelContext) -> None:
        self._learner = cast(Learner, ctx.instance)
        self.form_title = f"Register {self._learner.user.display_name} for a course"

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
        data = request.POST if request.method == "POST" else None
        return LearnerCourseRegistrationForm(data, learner=self._learner)

    def form_valid(self, request: HttpRequest, form: forms.ModelForm) -> HttpResponse:
        register_for_course(self._learner, form.cleaned_data["course"])
        return _registration_changed_response(self._learner)


class UnregisterLearnerFromCourseAction(PanelAction):
    """Withdraws one of the learner's active individual registrations, after
    confirmation. The registration travels as a `registration` parameter, so
    the action resolves on the registrations card and renders per row there,
    never as a footer button."""

    label = "Unregister"
    action_name = "unregister_from_course"
    variant = "secondary"
    renders_in_footer = False
    capability = "freedom_ls_learner_management.change_learnercourseregistration"
    trigger_template_name = "panel_framework/partials/modal_trigger.html"
    template_name = "educator_interface/modal/unregister_from_course_confirmation.html"

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

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
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
        context = super().get_context_data(ctx)
        context.update(
            {
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
                "confirm_url": self.get_action_url(ctx),
            }
        )
        return context

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        learner = cast(Learner, ctx.instance)
        unregister_from_course(learner, self._registration(ctx).course)
        return _registration_changed_response(learner)


class ReregisterLearnerForCourseAction(PanelAction):
    """Reactivates one of the learner's inactive individual registrations,
    after confirmation. Like unregistering, the registration travels as a
    `registration` parameter and the action renders per row."""

    label = "Re-register"
    action_name = "reregister_for_course"
    variant = "secondary"
    renders_in_footer = False
    capability = "freedom_ls_learner_management.change_learnercourseregistration"
    trigger_template_name = "panel_framework/partials/modal_trigger.html"
    template_name = "educator_interface/modal/reregister_confirmation.html"

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

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        registration = self._registration(ctx)
        context = super().get_context_data(ctx)
        context.update(
            {
                "learner": cast(Learner, ctx.instance),
                "registration": registration,
                "course": registration.course,
                "confirm_url": self.get_action_url(ctx),
            }
        )
        return context

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        learner = cast(Learner, ctx.instance)
        register_for_course(learner, self._registration(ctx).course)
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
        return _membership_changed_response(ids, ids)


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

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        learner, source = self._pair(ctx)
        context = super().get_context_data(ctx)
        if not CohortMembership.objects.filter(learner=learner, cohort=source).exists():
            context.update({"learner": learner, "cohort": source, "not_a_member": True})
            return context
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
        if not CohortMembership.objects.filter(learner=learner, cohort=source).exists():
            return render(
                ctx.request,
                self.template_name,
                self.get_context_data(ctx),
                status=422,
            )
        form = self._picker(ctx, learner)
        if not form.is_valid():
            return self._refusal(ctx, "Choose a cohort to move them to.")
        destination = cast(Cohort, form.cleaned_data["destination"])
        if not can(ctx.request.user, ADD_COHORTMEMBERSHIP, destination):
            return denied_response(ctx, self)
        for cohort in (source, destination):
            if not cohort.is_active:
                return inactive_cohort_response(ctx.request, cohort)
        try:
            move_between_cohorts(learner, source, destination)
        except ValueError as error:
            return self._refusal(ctx, str(error))
        ids = [str(learner.pk), str(source.pk), str(destination.pk)]
        return _membership_changed_response(ids, ids)

    def _refusal(self, ctx: PanelContext, reason: str) -> HttpResponse:
        context = self.get_context_data(ctx)
        if context.get("empty_message") or context.get("not_a_member"):
            return render(ctx.request, self.template_name, context, status=422)
        context["refusal"] = reason
        # The re-rendered select offers what the fresh dialog offered.
        form = cast(CohortPickerForm, context["form"])
        learner, _ = self._pair(ctx)
        cast(
            forms.ModelChoiceField, form.fields["destination"]
        ).queryset = _joinable_cohorts(ctx, learner)
        return render(ctx.request, self.template_name, context, status=422)


ADD_LEARNER = "freedom_ls_learner_management.add_learner"


def _empty_message(form: forms.BaseForm, field_name: str, message: str) -> str | None:
    """`message` when the picker's field offers nothing, otherwise None."""
    queryset = cast(forms.ModelChoiceField, form.fields[field_name]).queryset
    return None if queryset is not None and queryset.exists() else message


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


class AddToCohortAction(PanelAction):
    """Adds the learner on the page to an active cohort the user may add to."""

    label = "Add to cohort"
    action_name = "add_to_cohort"
    variant = "secondary"
    capability = ADD_COHORTMEMBERSHIP
    trigger_template_name = "panel_framework/partials/modal_trigger.html"
    template_name = "panel_framework/modal/form.html"
    _BUTTON = {
        "label": "Add to cohort",
        "variant": "primary",
        "loading_text": "Adding...",
    }

    def _form(self, ctx: PanelContext) -> CohortPickerForm:
        return _cohort_picker(ctx, cast(Learner, ctx.instance), None)

    def _title(self, ctx: PanelContext) -> str:
        return f"Add {cast(Learner, ctx.instance).user.display_name} to a cohort"

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        form = self._form(ctx)
        name = cast(Learner, ctx.instance).user.display_name
        return form_fragment_context(
            form,
            form_title=self._title(ctx),
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
                self, ctx, form, title=self._title(ctx), button=self._BUTTON, status=422
            )
        cohort = cast(Cohort, form.cleaned_data["cohort"])
        if not can(ctx.request.user, ADD_COHORTMEMBERSHIP, cohort):
            return denied_response(ctx, self)
        if not cohort.is_active:
            return inactive_cohort_response(ctx.request, cohort)
        learner = cast(Learner, ctx.instance)
        add_to_cohort(learner, cohort)
        return _membership_changed_response([str(learner.pk)], [str(cohort.pk)])


class AddExistingLearnersAction(RequiresActiveCohortMixin, PanelAction):
    """Adds existing learners to the cohort on the page, for a user who may
    add cohort members but not create learners."""

    label = "Add learners"
    action_name = "add_existing_learners"
    variant = "secondary"
    capability = ADD_COHORTMEMBERSHIP
    trigger_template_name = "panel_framework/partials/modal_trigger.html"
    template_name = "panel_framework/modal/form.html"
    _BUTTON = {
        "label": "Add learners",
        "variant": "primary",
        "loading_text": "Adding...",
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
                add_to_cohort(learner, cohort)
        return _membership_changed_response(
            [str(learner.pk) for learner in learners], [str(cohort.pk)]
        )


class AddLearnersAction(PanelAction):
    """Adds pasted email addresses as learners of the organisation, making a
    pending account for each unknown address, and optionally puts them in a
    cohort. The results come back in the modal, which stays open."""

    label = "Add learners"
    action_name = "add_learners"
    capability = ADD_LEARNER
    trigger_template_name = "panel_framework/partials/modal_trigger.html"
    template_name = "panel_framework/modal/form.html"
    _BUTTON = {
        "label": "Add learners",
        "variant": "primary",
        "loading_text": "Adding...",
    }

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

    def _form(self, ctx: PanelContext, preset: Cohort | None) -> AddLearnersForm:
        return AddLearnersForm(
            ctx.request.POST if ctx.request.method == "POST" else None,
            cohorts=self._cohorts(ctx),
            preset=preset,
        )

    def _form_url(self, ctx: PanelContext, preset: Cohort | None) -> str:
        url = self.get_action_url(ctx)
        if preset is not None and not isinstance(ctx.instance, Cohort):
            return f"{url}?cohort={preset.pk}"
        return url

    def _fragment_context(
        self, ctx: PanelContext, form: AddLearnersForm, preset: Cohort | None
    ) -> dict[str, object]:
        return form_fragment_context(
            form,
            form_title=f"Add learners to {preset}" if preset else "Add learners",
            form_url=self._form_url(ctx, preset),
            submit_buttons=[self._BUTTON],
        )

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
            results = add_learners(organisation, form.cleaned_data["entries"], cohort)
        except ValueError:
            return inactive_cohort_response(ctx.request, cast(Cohort, cohort))
        html = render_to_string(
            "educator_interface/modal/add_learners_results.html",
            {"results": results, "cohort": cohort},
            request=ctx.request,
        )
        events = {
            LEARNER_CHANGED: [
                str(result.learner.pk) for result in results if result.learner
            ]
        }
        if cohort is not None:
            events[COHORT_CHANGED] = [str(cohort.pk)]
        response = HttpResponse(html)
        response["HX-Trigger"] = build_hx_trigger(events)
        return response


class AddLearnersToCohortAction(RequiresActiveCohortMixin, AddLearnersAction):
    """Add learners on a cohort's page, with the cohort preset. Offered only
    to a user who may create learners; others get the existing-learner picker."""

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
}

OTHER_SITE_MESSAGE = (
    "This address belongs to an account on another site. Use a different address."
)


def _organisation(ctx: PanelContext) -> Organisation:
    return cast("OrganisationScopedRequest", ctx.request).organisation


def _refused(ctx: PanelContext, message: str) -> HttpResponse:
    """The 422 message a member dialog shows in place of its body."""
    return render(
        ctx.request,
        "educator_interface/modal/member_change_refused.html",
        {"message": message},
        status=422,
    )


def refusal_response(
    ctx: PanelContext, action: PanelAction, refused: RoleChangeRefused, name: str
) -> HttpResponse:
    """What a refused role change answers with: the 403 denied fragment for
    a missing capability, else a 422 message inside the dialog."""
    if refused.reason == RefusalReason.NOT_PERMITTED:
        return denied_response(ctx, action)
    return _refused(ctx, REFUSAL_MESSAGES[refused.reason].format(name=name))


def _member_name(user: User | None, email: str) -> str:
    """What the dialog calls the person: their name, or the address of an
    account not yet created."""
    return email if user is None else user.display_name


def member_changed_response(user: User) -> HttpResponse:
    return changed_response({MEMBER_CHANGED: [str(user.pk)]})


def member_state(user: User | None, organisation: Organisation) -> str:
    """Where a role given now would land: "new" for an account not yet
    created, "missing" for one with no OrganisationMember row here,
    "inactive" for a suspended row, else "active"."""
    if user is None:
        return "new"
    member = OrganisationMember.objects.filter(
        organisation=organisation, user=user
    ).first()
    if member is None:
        return "missing"
    if not member.is_active:
        return "inactive"
    return "active"


def _entries_after(
    before: list[RoleEntry],
    grantor: User,
    role: str,
    display_name: str,
    cohorts: list[Cohort],
) -> list[RoleEntry]:
    """`before` with `role` on `cohorts` merged in, in MEMBER_ROLES order."""
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
    return [held[key] for key in MEMBER_ROLES if key in held]


class AddMemberAction(PanelAction):
    """Gives an existing account a member role, in a dialog of steps: look up
    the address, choose the role, confirm. Nothing is written until the
    confirmation is submitted."""

    label = "Add member"
    action_name = "add_member"
    capability = "freedom_ls_learner_management.add_organisationmember"
    trigger_template_name = "panel_framework/partials/modal_trigger.html"
    template_name = "educator_interface/modal/add_member.html"
    #: Every role this dialog could offer. A role missing from the grantor's
    #: grantable roles counts as withheld only when it is in here.
    offerable_roles: tuple[str, ...] = MEMBER_ROLES

    def permission_object(self, ctx: PanelContext) -> Model | None:
        return _organisation(ctx)

    def is_offered(self, ctx: PanelContext) -> bool:
        return bool(self._grantable(ctx))

    def _grantable(self, ctx: PanelContext) -> list[GrantableRole]:
        return grantable_roles_for(ctx.request)

    def _preset(self, ctx: PanelContext) -> Cohort | None:
        return None

    def _dialog_title(self, ctx: PanelContext) -> str:
        preset = self._preset(ctx)
        return f"Add a member to {preset}" if preset else "Add a member"

    def _email_step(
        self, ctx: PanelContext, form: MemberEmailForm, status: int = 200
    ) -> HttpResponse:
        return render(
            ctx.request,
            self.template_name,
            {
                "step": "email",
                "dialog_title": self._dialog_title(ctx),
                "form": form,
                "form_url": self.get_action_url(ctx),
            },
            status=status,
        )

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        return {
            "step": "email",
            "dialog_title": self._dialog_title(ctx),
            "form": MemberEmailForm(),
            "form_url": self.get_action_url(ctx),
        }

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        if not self._grantable(ctx):
            return denied_response(ctx, self)
        if ctx.request.POST.get("step") == "lookup":
            return self._lookup(ctx)
        return self._submit(ctx)

    def _other_site_response(self, ctx: PanelContext) -> HttpResponse:
        form = MemberEmailForm(ctx.request.POST)
        form.is_valid()
        form.add_error("email", OTHER_SITE_MESSAGE)
        return self._email_step(ctx, form, status=422)

    def _match(self, ctx: PanelContext, email: str) -> User | HttpResponse | None:
        """The account for `email`, None when there is none yet, or the
        response that says why the address cannot be used."""
        try:
            user = lookup_user(_organisation(ctx).site, email)
        except EmailInUseOnAnotherSite:
            return self._other_site_response(ctx)
        return user

    def _role_cards(self, ctx: PanelContext) -> list[dict[str, str | bool]]:
        config = get_role_config(_organisation(ctx).site.name)
        return [
            {
                "key": grantable.role,
                "display_name": config[grantable.role].display_name,
                "description": config[grantable.role].description,
                "needs_cohorts": grantable.cohorts is not None,
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

    def _role_step(
        self,
        ctx: PanelContext,
        user: User | None,
        form: AddMemberForm,
        status: int = 200,
    ) -> HttpResponse:
        chosen = [str(pk) for pk in form["cohorts"].value() or []]
        return render(
            ctx.request,
            self.template_name,
            {
                "step": "role",
                "dialog_title": self._dialog_title(ctx),
                "match": user,
                "new_account": user is None,
                "form": form,
                "form_url": self.get_action_url(ctx),
                "role_cards": self._role_cards(ctx),
                "preset_cohort": self._preset(ctx),
                "cohort_rows": self._cohort_rows(ctx, chosen),
                "selected_role": form["role"].value() or "",
                "role_note": self._role_note(ctx),
            },
            status=status,
        )

    def _lookup(self, ctx: PanelContext) -> HttpResponse:
        email_form = MemberEmailForm(ctx.request.POST)
        if not email_form.is_valid():
            return self._email_step(ctx, email_form, status=422)
        matched = self._match(ctx, email_form.cleaned_data["email"])
        if isinstance(matched, HttpResponse):
            return matched
        form = AddMemberForm(
            None,
            roles=[
                (grantable.role, grantable.role) for grantable in self._grantable(ctx)
            ],
            cohorts=self._cohort_choices(ctx),
            preset=self._preset(ctx),
            new_account=matched is None,
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
        matched = self._match(ctx, ctx.request.POST.get("email", ""))
        if isinstance(matched, HttpResponse):
            return matched
        form = AddMemberForm(
            ctx.request.POST,
            roles=[(role, role) for role in MEMBER_ROLES],
            cohorts=self._cohort_choices(ctx),
            preset=self._preset(ctx),
            new_account=matched is None,
        )
        if not form.is_valid():
            return self._role_step(ctx, matched, form, status=422)
        role = cast(str, form.cleaned_data["role"])
        cohorts = sorted(form.cleaned_data["cohorts"], key=lambda c: c.name)
        targets = self._targets(ctx, role, cohorts)
        if targets is None:
            return denied_response(ctx, self)
        email = cast(str, form.cleaned_data["email"])
        before = (
            [] if matched is None else current_role_entries(matched, _organisation(ctx))
        )
        if role == "organisation_admin" and any(e.role == role for e in before):
            return _refused(
                ctx,
                f"{_member_name(matched, email)} is already an organisation admin here.",
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
                f"{_member_name(matched, email)} already holds this role on "
                "these cohorts.",
            )
        new_targets: list[Organisation | Cohort] = [*new_cohorts] or targets
        if ctx.request.POST.get("confirmed") != "1":
            return self._confirmation(
                ctx, email, matched, role, new_cohorts, held, cohorts, names, before
            )
        return self._perform(ctx, matched, email, role, new_targets, names)

    def _already_held(
        self, ctx: PanelContext, user: User | None, role: str, cohorts: list[Cohort]
    ) -> list[Cohort]:
        """The cohorts among `cohorts` that `user` already holds `role` on."""
        if user is None or not cohorts:
            return []
        held_keys = set(
            member_assignments(_organisation(ctx))
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
        name = _member_name(user, email)
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
        before_pairs = (
            set()
            if user is None
            else {
                (assignment.role, assignment.object_id)
                for assignment in member_assignments(organisation).filter(user=user)
            }
        )
        new_keys = [str(cohort.pk) for cohort in cohorts] or [str(organisation.pk)]
        after_pairs = before_pairs | {(role, key) for key in new_keys}
        return render(
            ctx.request,
            self.template_name,
            {
                "step": "confirmation",
                "match": user,
                "member_name": name,
                "creates_account": user is None,
                "first_name": names[0],
                "last_name": names[1],
                "form_url": self.get_action_url(ctx),
                "email": email,
                "role": role,
                "cohort_ids": [str(cohort.pk) for cohort in chosen],
                "already_held": join_prose([cohort.name for cohort in already_held]),
                "widening": user is not None and is_widening(before_pairs, after_pairs),
                "display_name": role_config.display_name,
                "description": role_config.description,
                "scope": (
                    ORGANISATION_SCOPE
                    if role == "organisation_admin"
                    else join_prose([cohort.name for cohort in cohorts])
                ),
                "current_entries": before,
                "after_entries": after,
                "member_state": member_state(user, organisation),
                "site_level": user is not None and is_site_level_admin(user, site),
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
        name = _member_name(user, email)
        try:
            with transaction.atomic():
                user, created = match_or_create_user(organisation.site, email, *names)
                for target in targets:
                    assign_role(cast("User", ctx.request.user), user, role, target)
                if created:
                    send_account_setup_email(user, organisation.name)
        except RoleChangeRefused as refused:
            return refusal_response(ctx, self, refused, name)
        except EmailInUseOnAnotherSite:
            return self._other_site_response(ctx)
        return member_changed_response(user)


class AddMemberToCohortAction(AddMemberAction):
    """Add a member on a cohort's page, with the cohort fixed."""

    capability = "freedom_ls_role_based_permissions.assign_cohort_viewer"
    offerable_roles = ("cohort_admin", "cohort_viewer")

    def permission_object(self, ctx: PanelContext) -> Model | None:
        return ctx.instance

    def _grantable(self, ctx: PanelContext) -> list[GrantableRole]:
        cohort = cast(Cohort, ctx.instance)
        return [
            grantable
            for grantable in grantable_roles_for(ctx.request)
            if grantable.cohorts is not None and cohort in grantable.cohorts
        ]

    def _preset(self, ctx: PanelContext) -> Cohort | None:
        return cast(Cohort, ctx.instance)


class MemberRoleAction(PanelAction):
    """An action on one role entry of one member, named by the `user` and
    `role` parameters. Renders per entry, never in the header. The target
    is re-read on every request through members_of, so a member who has
    since lost every role, or a role no longer held, is a 404 that the
    action route answers with its unavailable fragment."""

    variant = "secondary"
    renders_in_footer = False
    trigger_template_name = "panel_framework/partials/modal_trigger.html"

    def get_capability(self, ctx: PanelContext) -> str | None:
        role = _action_params(ctx.request).get("role", "")
        if role in MEMBER_ROLES:
            return ASSIGN.format(role=role)
        return ASSIGN.format(role="cohort_viewer")

    def permission_object(self, ctx: PanelContext) -> Model | None:
        return _organisation(ctx)

    def _entries(self, ctx: PanelContext, user: User) -> list[RoleEntry]:
        """Every role `user` holds here, loaded once per request."""
        return current_role_entries(user, _organisation(ctx))

    def _entry(self, ctx: PanelContext, entries: list[RoleEntry]) -> RoleEntry:
        """The entry the `role` parameter names, from `entries`."""
        role = _action_params(ctx.request).get("role", "")
        for entry in entries:
            if entry.role == role:
                return entry
        raise Http404("The member does not hold this role")


class RemoveRoleAction(MemberRoleAction):
    label = "Remove"
    action_name = "remove_role"
    template_name = "educator_interface/modal/remove_role_confirmation.html"

    def _kept(
        self,
        ctx: PanelContext,
        user: User,
        removed: RoleEntry,
        entries: list[RoleEntry],
    ) -> str:
        organisation = _organisation(ctx)
        kept = [
            f"{entry.display_name} on {entry.scope}"
            for entry in entries
            if entry.role != removed.role
        ]
        has_learner = Learner.objects.filter(
            organisation=organisation, user=user, is_active=True
        ).exists()
        parts = ["their account", *kept]
        if has_learner:
            parts.append("their learner access in this organisation")
        return join_prose(parts)

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        organisation = _organisation(ctx)
        site = organisation.site
        grantor = cast("User", ctx.request.user)
        user = _member_param(ctx)
        entries = self._entries(ctx, user)
        entry = self._entry(ctx, entries)
        description = get_role_config(site.name)[entry.role].description.rstrip(".")
        return {
            "member": user,
            "entry": entry,
            "description": description,
            "full_scope": (
                entry.full_scope
                if entry.role == "organisation_admin"
                else join_prose([cohort.name for cohort in entry.cohorts])
            ),
            "keeps": self._kept(ctx, user, entry, entries),
            "last_organisation_admin": entry.role == "organisation_admin"
            and is_last_organisation_admin(organisation, user),
            "grantor_is_site_level": is_site_level_admin(grantor, site),
            "target_is_site_level": is_site_level_admin(user, site),
            "confirm_url": self.get_action_url(ctx),
        }

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        organisation = _organisation(ctx)
        user = _member_param(ctx)
        entry = self._entry(ctx, self._entries(ctx, user))
        targets: list[Organisation | Cohort] = (
            [organisation] if entry.role == "organisation_admin" else [*entry.cohorts]
        )
        try:
            with transaction.atomic():
                for target in targets:
                    remove_role(
                        cast("User", ctx.request.user), user, entry.role, target
                    )
        except RoleChangeRefused as refused:
            return refusal_response(ctx, self, refused, user.display_name)
        return member_changed_response(user)


class CohortChange(NamedTuple):
    added: list[Cohort]
    removed: list[Cohort]
    untouched: list[Cohort]


class ChangeCohortsAction(MemberRoleAction):
    """Adds and removes the cohorts of one cohort-role entry in a single
    transaction, after a confirmation that names what is gained and lost."""

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
            "member": user,
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
                for cohort in entry.cohorts
                if cohort not in offered
            ],
        }

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        user = _member_param(ctx)
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
        user = _member_param(ctx)
        grantor = cast("User", ctx.request.user)
        entry = self._entry(ctx, self._entries(ctx, user))
        chosen = self._chosen(ctx, entry)
        if user == grantor:
            return _refused(ctx, REFUSAL_MESSAGES[RefusalReason.SELF])
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
                    remove_role(grantor, user, entry.role, cohort)
        except RoleChangeRefused as refused:
            return refusal_response(ctx, self, refused, user.display_name)
        return member_changed_response(user)

    def _confirmation(
        self,
        ctx: PanelContext,
        user: User,
        entry: RoleEntry,
        chosen: list[Cohort],
        plan: CohortChange,
    ) -> HttpResponse:
        organisation = _organisation(ctx)
        before = {(entry.role, str(cohort.pk)) for cohort in entry.cohorts}
        after = (before - {(entry.role, str(c.pk)) for c in plan.removed}) | {
            (entry.role, str(c.pk)) for c in plan.added
        }
        return render(
            ctx.request,
            self.template_name,
            {
                "step": "confirmation",
                "member": user,
                "entry": entry,
                "form_url": self.get_action_url(ctx),
                "cohort_ids": [str(cohort.pk) for cohort in chosen],
                "added": join_prose([cohort.name for cohort in plan.added]),
                "removed": join_prose([cohort.name for cohort in plan.removed]),
                "widening": is_widening(before, after),
                "removes_role": not plan.added
                and len(plan.removed) == len(entry.cohorts),
                "member_state": member_state(user, organisation),
            },
        )


class MemberStateAction(PanelAction):
    """Flips one member's OrganisationMember row, named by the `user`
    parameter, after confirmation. Renders per row, never in the header."""

    variant = "secondary"
    renders_in_footer = False
    capability = CHANGE_MEMBER
    trigger_template_name = "panel_framework/partials/modal_trigger.html"

    def permission_object(self, ctx: PanelContext) -> Model | None:
        return _organisation(ctx)

    def _row(self, user: User, organisation: Organisation) -> OrganisationMember | None:
        return OrganisationMember.objects.filter(
            user=user, organisation=organisation
        ).first()


class SuspendMemberAction(MemberStateAction):
    label = "Suspend"
    action_name = "suspend"
    template_name = "educator_interface/modal/suspend_member_confirmation.html"

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        organisation = _organisation(ctx)
        user = _member_param(ctx)
        return {
            "member": user,
            "organisation": organisation,
            "last_organisation_admin": is_last_organisation_admin(organisation, user),
            "grantor_is_site_level": is_site_level_admin(
                cast("User", ctx.request.user), organisation.site
            ),
            "confirm_url": self.get_action_url(ctx),
        }

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        organisation = _organisation(ctx)
        user = _member_param(ctx)
        row = self._row(user, organisation)
        if row is None or not row.is_active:
            raise Http404("The member is already suspended")
        try:
            set_organisation_member_active(cast("User", ctx.request.user), row, False)
        except RoleChangeRefused as refused:
            return refusal_response(ctx, self, refused, user.display_name)
        return member_changed_response(user)


class ReactivateMemberAction(MemberStateAction):
    label = "Reactivate"
    action_name = "reactivate"
    template_name = "educator_interface/modal/reactivate_member_confirmation.html"

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        user = _member_param(ctx)
        entries = current_role_entries(user, _organisation(ctx))
        return {
            "member": user,
            "roles": join_prose(
                [f"{entry.display_name} on {entry.scope}" for entry in entries]
            ),
            "confirm_url": self.get_action_url(ctx),
        }

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        organisation = _organisation(ctx)
        user = _member_param(ctx)
        row = self._row(user, organisation)
        if row is not None and row.is_active:
            raise Http404("The member is already active")
        try:
            with transaction.atomic():
                row = row or ensure_organisation_member(user, organisation)
                set_organisation_member_active(
                    cast("User", ctx.request.user), row, True
                )
        except RoleChangeRefused as refused:
            return refusal_response(ctx, self, refused, user.display_name)
        return member_changed_response(user)
