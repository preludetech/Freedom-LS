"""The panel actions on a learner."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from panel_framework.actions import (
    ConfirmAction,
    EditAction,
    FormPanelAction,
    ModalPanelAction,
    PanelAction,
    changed_response,
    current_page_within,
    denied_response,
    join_prose,
    navigation_response,
    refusal_response,
)
from panel_framework.context import PanelContext
from panel_framework.events import build_hx_trigger

from django import forms
from django.db import transaction
from django.db.models import Model, QuerySet
from django.http import (
    HttpResponse,
    HttpResponseNotAllowed,
)
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import urlencode

from freedom_ls.accounts.account_setup import (
    AccountAlreadySetUp,
    SetupEmailRecentlySent,
    is_pending,
    resend_account_setup_email,
)
from freedom_ls.accounts.config import config as accounts_config
from freedom_ls.accounts.models import User, display_name_for
from freedom_ls.educator_interface.events import (
    COHORT_CHANGED,
    LEARNER_CHANGED,
)
from freedom_ls.educator_interface.forms import (
    AddLearnerForm,
    CohortPickerForm,
    LearnerCourseRegistrationForm,
    LearnerNameForm,
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
    inactive_cohort_response,
)
from freedom_ls.educator_interface.panels.common.registration_actions import (
    LearnerRegistrationDeactivation,
    LearnerRegistrationReactivation,
    registration_changed_response,
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
    deactivate_learner,
    move_between_cohorts,
    reactivate_learner,
    record_learner_entry,
    register_for_course,
    remove_from_cohort,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.queries import (
    ADD_COHORTMEMBERSHIP,
    ADD_LEARNER,
    cohorts_visible_to,
    courses_gaining_access,
    courses_losing_access,
    learners_visible_to,
)
from freedom_ls.learner_progress.utils import move_progress_preview
from freedom_ls.organisations.utils import get_default_organisation

__all__ = [
    "AddLearnerAction",
    "AddToCohortAction",
    "DeactivateLearnerAction",
    "DeactivateRegistrationAction",
    "EditLearnerNameAction",
    "ImportLearnersAction",
    "LearnerStateAction",
    "MembershipAction",
    "MoveToCohortAction",
    "ReactivateLearnerAction",
    "ReactivateRegistrationAction",
    "RegisterLearnerForCourseAction",
    "RemoveFromCohortAction",
    "ResendSetupEmailAction",
    "_cohort_picker",
    "_joinable_cohorts",
    "_membership_changed_response",
    "_picker_cohorts",
    "learner_state_actions",
    "record_and_resend_setup_email",
]


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
        return registration_changed_response(learner)


class DeactivateRegistrationAction(
    EducatorReasonMixin, LearnerRegistrationDeactivation
):
    """Deactivates one of the learner's active individual registrations, from
    the registrations card, where it renders per row and never as a footer
    button."""

    def registration_scope(
        self, ctx: PanelContext
    ) -> QuerySet[LearnerCourseRegistration]:
        return LearnerCourseRegistration.objects.filter(
            learner=cast(Learner, ctx.instance)
        )


class ReactivateRegistrationAction(LearnerRegistrationReactivation):
    """Reactivates one of the learner's inactive individual registrations, from
    the registrations card, where it renders per row."""

    def registration_scope(
        self, ctx: PanelContext
    ) -> QuerySet[LearnerCourseRegistration]:
        return LearnerCourseRegistration.objects.filter(
            learner=cast(Learner, ctx.instance)
        )


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
