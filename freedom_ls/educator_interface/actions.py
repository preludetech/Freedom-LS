"""Panel actions on a cohort that need more than the generic framework ones."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, cast
from uuid import UUID

from django import forms
from django.db import transaction
from django.db.models import Model, QuerySet
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string

from freedom_ls.accounts.account_setup import (
    AccountAlreadySetUp,
    SetupEmailRecentlySent,
    is_pending,
    resend_account_setup_email,
)
from freedom_ls.accounts.config import config as accounts_config
from freedom_ls.educator_interface.events import (
    COHORT_CHANGED,
    LEARNER_CHANGED,
    REGISTRATION_CHANGED,
)
from freedom_ls.educator_interface.forms import (
    AddLearnersForm,
    CohortCourseRegistrationForm,
    CohortPickerForm,
    LearnerCourseRegistrationForm,
    LearnerNameForm,
    LearnerPickerForm,
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
)
from freedom_ls.learner_management.queries import (
    ADD_COHORTMEMBERSHIP,
    cohort_course_count,
    cohort_is_empty,
    cohort_learner_count,
    cohorts_visible_to,
    courses_gaining_access,
    courses_losing_access,
    learners_visible_to,
    members_keeping_access,
    other_grants_for,
)
from freedom_ls.learner_management.utils import (
    register_cohort_for_course,
    unregister_cohort_from_course,
)
from freedom_ls.learner_progress.utils import move_progress_preview
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.panel_framework.actions import (
    DeleteAction,
    EditAction,
    FormPanelAction,
    PanelAction,
    count_noun,
    count_phrase,
    denied_response,
    form_fragment_context,
    join_prose,
    navigation_response,
)
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.events import build_hx_trigger

if TYPE_CHECKING:
    from freedom_ls.educator_interface.views import OrganisationScopedRequest


def _uuid_from(params: Mapping[str, str], name: str) -> UUID:
    try:
        return UUID(params.get(name, ""))
    except ValueError:
        raise Http404(f"No such {name}") from None


def _uuid_param(request: HttpRequest, name: str) -> UUID:
    """A UUID the action's trigger sent along: from the form on a submit, from
    the query string otherwise. A missing or malformed value is a 404."""
    return _uuid_from(request.POST if request.method == "POST" else request.GET, name)


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
        response = HttpResponse(status=204)
        response["HX-Trigger"] = build_hx_trigger(
            {LEARNER_CHANGED: [str(learner.pk)]}, close_modal=True
        )
        return response


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
    response = HttpResponse(status=204)
    response["HX-Trigger"] = build_hx_trigger(
        {REGISTRATION_CHANGED: ids, LEARNER_CHANGED: ids}, close_modal=True
    )
    return response


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
        context = super().get_context_data(ctx)
        context.update(
            {
                "learner": learner,
                "registration": registration,
                "course": registration.course,
                "keeping_cohorts": join_prose(
                    [
                        cohort.name
                        for cohort in other_grants_for(learner, registration.course)
                    ]
                ),
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


class MoveToCohortAction(MembershipAction):
    """Moves a learner from the cohort on the row to an active cohort the user
    may add to. Choosing a destination re-renders the fragment with what the
    move changes."""

    label = "Move to another cohort"
    action_name = "move"
    capability = "freedom_ls_learner_management.delete_cohortmembership"
    template_name = "educator_interface/modal/move_confirmation.html"

    def _offered(self, ctx: PanelContext, learner: Learner) -> QuerySet[Cohort]:
        scoped = cast("OrganisationScopedRequest", ctx.request)
        return (
            cohorts_visible_to(
                scoped.user, scoped.organisation, capability=ADD_COHORTMEMBERSHIP
            )
            .filter(is_active=True)
            .exclude(cohortmembership__learner=learner)
        )

    def _picker(self, ctx: PanelContext, learner: Learner) -> CohortPickerForm:
        scoped = cast("OrganisationScopedRequest", ctx.request)
        if ctx.request.method == "POST":
            # Wider than the offered set, so a cohort the user may see but not
            # add to reaches the permission check and is refused as a denial.
            queryset = Cohort.objects.filter(organisation=scoped.organisation)
            data: Mapping[str, str] | None = ctx.request.POST
        else:
            queryset = self._offered(ctx, learner)
            data = ctx.request.GET if "destination" in ctx.request.GET else None
        return CohortPickerForm(
            data,
            queryset=queryset.exclude(cohortmembership__learner=learner),
            field_name="destination",
        )

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        learner, source = self._pair(ctx)
        context = super().get_context_data(ctx)
        if not CohortMembership.objects.filter(learner=learner, cohort=source).exists():
            context.update({"learner": learner, "cohort": source, "not_a_member": True})
            return context
        if not self._offered(ctx, learner).exists():
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
        response = HttpResponse(status=204)
        response["HX-Trigger"] = build_hx_trigger(
            {LEARNER_CHANGED: ids, COHORT_CHANGED: ids}, close_modal=True
        )
        return response

    def _refusal(self, ctx: PanelContext, reason: str) -> HttpResponse:
        context = self.get_context_data(ctx)
        if context.get("empty_message"):
            return render(ctx.request, self.template_name, context, status=422)
        context["refusal"] = reason
        # The re-rendered select offers what the fresh dialog offered.
        form = cast(CohortPickerForm, context["form"])
        learner, _ = self._pair(ctx)
        cast(
            forms.ModelChoiceField, form.fields["destination"]
        ).queryset = self._offered(ctx, learner)
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


def _membership_changed_response(
    learner_ids: list[str], cohort_id: str
) -> HttpResponse:
    response = HttpResponse(status=204)
    response["HX-Trigger"] = build_hx_trigger(
        {LEARNER_CHANGED: learner_ids, COHORT_CHANGED: [cohort_id]}, close_modal=True
    )
    return response


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
        scoped = cast("OrganisationScopedRequest", ctx.request)
        learner = cast(Learner, ctx.instance)
        if ctx.request.method == "POST":
            # Wider than the offered set, so a cohort the user may see but not
            # add to reaches the permission check and is refused as a denial.
            queryset = Cohort.objects.filter(organisation=scoped.organisation)
            data = ctx.request.POST
        else:
            queryset = cohorts_visible_to(
                scoped.user, scoped.organisation, capability=ADD_COHORTMEMBERSHIP
            ).filter(is_active=True)
            data = None
        return CohortPickerForm(
            data, queryset=queryset.exclude(cohortmembership__learner=learner)
        )

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
        return _membership_changed_response([str(learner.pk)], str(cohort.pk))


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
            [str(learner.pk) for learner in learners], str(cohort.pk)
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
