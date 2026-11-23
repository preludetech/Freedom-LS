"""The bulk actions over the cohorts table."""

from __future__ import annotations

from typing import cast

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.db.models import Model, QuerySet
from django.http import HttpRequest

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.panels.common.bulk_actions import (
    CoursePickerMixin,
    EducatorBulkAction,
)
from freedom_ls.learner_management.learner_actions import (
    deactivate_cohort,
    reactivate_cohort,
)
from freedom_ls.learner_management.models import Cohort, CohortCourseRegistration
from freedom_ls.learner_management.queries import (
    ADD_COHORTCOURSEREGISTRATION,
    CHANGE_COHORT,
    CHANGE_COHORTCOURSEREGISTRATION,
    cohorts_visible_to,
)
from freedom_ls.learner_management.utils import (
    deactivate_cohort_registration,
    register_cohort_for_course,
)
from freedom_ls.organisations.models import Organisation
from freedom_ls.panel_framework.actions import count_noun
from freedom_ls.panel_framework.bulk_actions import BulkOutcome, register_bulk_action

__all__ = [
    "CohortBulkAction",
    "CohortCourseBulkAction",
    "CohortStateBulkAction",
    "DeactivateCohortRegistrationBulkAction",
    "DeactivateCohortsBulkAction",
    "ReactivateCohortsBulkAction",
    "RegisterCohortForCourseBulkAction",
]


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
