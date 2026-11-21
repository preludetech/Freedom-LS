"""Panel actions on a cohort that need more than the generic framework ones."""

from __future__ import annotations

from typing import cast

from django import forms
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.db import transaction
from django.db.models import Model, QuerySet, prefetch_related_objects
from django.http import (
    HttpRequest,
    HttpResponse,
    QueryDict,
)
from django.shortcuts import get_object_or_404

from freedom_ls.accounts.account_setup import (
    AccountAlreadySetUp,
    SetupEmailRecentlySent,
    pending_user_q,
)
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.forms import (
    BulkTargetPickerForm,
    CohortCourseRegistrationForm,
    LearnerPickerForm,
)
from freedom_ls.educator_interface.panels.common.actions import (
    EducatorReasonMixin,
    _empty_message,
    _register_title,
    inactive_cohort_response,
)
from freedom_ls.educator_interface.panels.common.bulk_actions import (
    CoursePickerMixin,
    EducatorBulkAction,
)
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.educator_interface.panels.learner.actions import (
    AddLearnerAction,
    _membership_changed_response,
    record_and_resend_setup_email,
)
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.learner_actions import (
    add_to_cohort,
    deactivate_cohort,
    deactivate_learner,
    deactivate_registration,
    reactivate_cohort,
    reactivate_learner,
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
    DELETE_COHORTMEMBERSHIP,
    cohort_course_count,
    cohort_is_empty,
    cohort_learner_count,
    cohorts_visible_to,
    courses_lost_by_any,
    import_into_cohort_in_progress,
    learners_keeping_access_count,
    learners_permitted_for,
    learners_visible_to,
    members_keeping_access,
)
from freedom_ls.learner_management.utils import (
    deactivate_cohort_registration,
    record_cohort_entry,
    register_cohort_for_course,
)
from freedom_ls.organisations.models import Organisation
from freedom_ls.panel_framework.actions import (
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
from freedom_ls.panel_framework.bulk_actions import (
    BulkCount,
    BulkOutcome,
    register_bulk_action,
)
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.role_based_permissions.utils import delete_role_rows_for


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
