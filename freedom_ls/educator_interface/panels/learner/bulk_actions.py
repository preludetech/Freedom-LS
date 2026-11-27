"""The bulk actions over the learners table."""

from __future__ import annotations

from typing import cast

from panel_framework.actions import (
    count_noun,
    count_phrase,
    join_prose,
)
from panel_framework.bulk_actions import (
    BulkCount,
    BulkOutcome,
    register_bulk_action,
)

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.db.models import Model, QuerySet, prefetch_related_objects
from django.http import (
    HttpRequest,
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
)
from freedom_ls.educator_interface.panels.common.bulk_actions import (
    CoursePickerMixin,
    EducatorBulkAction,
)
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.educator_interface.panels.learner.actions import (
    record_and_resend_setup_email,
)
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.learner_actions import (
    add_to_cohort,
    deactivate_learner,
    deactivate_registration,
    reactivate_learner,
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
    ADD_LEARNERCOURSEREGISTRATION,
    CHANGE_LEARNER,
    CHANGE_LEARNERCOURSEREGISTRATION,
    DELETE_COHORTMEMBERSHIP,
    cohorts_visible_to,
    courses_lost_by_any,
    learners_keeping_access_count,
    learners_permitted_for,
)
from freedom_ls.organisations.models import Organisation

__all__ = [
    "AddToCohortBulkAction",
    "CohortMembershipBulkAction",
    "CourseRegistrationBulkAction",
    "DeactivateLearnersBulkAction",
    "DeactivateRegistrationBulkAction",
    "LearnerBulkAction",
    "LearnerStateBulkAction",
    "ReactivateLearnersBulkAction",
    "RegisterForCourseBulkAction",
    "RemoveFromCohortBulkAction",
    "ResendSetupEmailBulkAction",
]


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
    picks. `already_member_ids` holds the selected learners already in that cohort,
    read once per classification so previewing costs a fixed number of queries
    however many learners are selected."""

    form_class = BulkTargetPickerForm
    # The services refuse an inactive cohort, or one from another
    # organisation, with a ValueError; a cohort deactivated between the
    # confirmation and the run fails each learner instead of aborting the run.
    failure_exceptions = (ValueError,)
    already_member_ids: frozenset[object] = frozenset()

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
        self.already_member_ids = frozenset(
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
        return self.unchanged_reason if obj.pk in self.already_member_ids else None

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
        return None if obj.pk in self.already_member_ids else self.unchanged_reason

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
