"""Table filters specific to the educator interface's lists."""

from __future__ import annotations

from functools import reduce
from operator import or_
from typing import TYPE_CHECKING, cast

from django.db.models import Q, QuerySet
from django.http import HttpRequest

from freedom_ls.accounts.models import User
from freedom_ls.audit_log.actions import audit_actions, audit_actions_by_group
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.models import (
    CohortCourseRegistration,
    CohortMembership,
    Learner,
)
from freedom_ls.learner_management.queries import (
    STAFF_ROLES,
    VIEW_ORGANISATION_STAFF_ROLES,
    LearnerStatus,
    cohorts_visible_to,
    courses_visible_to,
    holds_registration_for_any_expression,
    learner_status_q,
    staff_assignments,
)
from freedom_ls.panel_framework.filters import (
    ChoiceFilter,
    RelatedChoiceFilter,
    TableFilter,
)
from freedom_ls.role_based_permissions.loader import get_role_config

if TYPE_CHECKING:
    from freedom_ls.educator_interface.views import OrganisationScopedRequest


class VisibleCourseFilter(RelatedChoiceFilter):
    """Narrows cohorts to those holding an active registration for a course
    the educator can see."""

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        scoped = cast("OrganisationScopedRequest", request)
        return courses_visible_to(scoped.user, scoped.organisation).order_by("title")

    def apply(
        self, request: HttpRequest, queryset: QuerySet, values: list[str]
    ) -> QuerySet:
        # A subquery rather than a join: the queryset carries a Count()
        # annotation that a join through the registrations would inflate, and
        # a cohort registered for two chosen courses must not repeat.
        return queryset.filter(
            pk__in=CohortCourseRegistration.objects.filter(
                course__in=values, is_active=True
            ).values("cohort_id")
        )


class LearnerStatusFilter(ChoiceFilter):
    """Narrows learners to the chosen statuses; active and pending while the
    parameter is absent."""

    def __init__(self) -> None:
        super().__init__(
            "status",
            "Status",
            choices=LearnerStatus.choices,
            default=(LearnerStatus.ACTIVE, LearnerStatus.PENDING),
            always_shown=True,
        )

    def apply(
        self, request: HttpRequest, queryset: QuerySet[Learner], values: list[str]
    ) -> QuerySet[Learner]:
        # filter_queryset only calls apply with at least one value.
        return queryset.filter(
            reduce(or_, (learner_status_q(LearnerStatus(v)) for v in values))
        )


class LearnerCohortFilter(RelatedChoiceFilter):
    """Narrows learners to members of the chosen cohorts; an inactive cohort is
    offered, labelled as inactive."""

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        scoped = cast("OrganisationScopedRequest", request)
        return cohorts_visible_to(scoped.user, scoped.organisation).order_by("name")

    def get_choices(self, request: HttpRequest) -> list[tuple[str, str]]:
        return [
            (
                str(cohort.pk),
                cohort.name if cohort.is_active else f"{cohort.name} (inactive)",
            )
            for cohort in self.get_queryset(request)
        ]

    def apply(
        self, request: HttpRequest, queryset: QuerySet[Learner], values: list[str]
    ) -> QuerySet[Learner]:
        return queryset.filter(
            pk__in=CohortMembership.objects.filter(cohort__in=values).values(
                "learner_id"
            )
        )


class LearnerCourseFilter(VisibleCourseFilter):
    """Narrows learners to those holding an active registration for a chosen
    course, individually or through an active cohort."""

    def apply(
        self, request: HttpRequest, queryset: QuerySet[Learner], values: list[str]
    ) -> QuerySet[Learner]:
        return queryset.filter(holds_registration_for_any_expression(None, values))


def may_see_staff_roles(request: HttpRequest) -> bool:
    """Whether the viewer may see which roles staff members hold, computed once
    and kept on the request because the roles cell, the Role filter's choices
    and its narrowing all ask. A viewer who may see names only must not learn
    who holds which role, so the filter withholds itself too."""
    scoped = cast("OrganisationScopedRequest", request)
    cached = getattr(scoped, "may_see_staff_roles", None)
    if cached is None:
        cached = can(scoped.user, VIEW_ORGANISATION_STAFF_ROLES, scoped.organisation)
        scoped.may_see_staff_roles = cached
    return cached


class StaffRoleFilter(ChoiceFilter):
    """Narrows staff to those holding a chosen role here; every role while
    the parameter is absent or "All roles" is among the values."""

    ALL = "all"
    widget = "select"

    def __init__(self) -> None:
        super().__init__("role", "Role", default=(self.ALL,), always_shown=True)

    def get_choices(self, request: HttpRequest) -> list[tuple[str, str]]:
        if not may_see_staff_roles(request):
            return []
        scoped = cast("OrganisationScopedRequest", request)
        config = get_role_config(scoped.organisation.site.name)
        return [
            (self.ALL, "All roles"),
            # A site that replaces the roles may leave some of these out.
            *(
                (role, config[role].display_name)
                for role in STAFF_ROLES
                if role in config
            ),
        ]

    def toggled(self, values: list[str], value: str) -> list[str]:
        # "All roles" is the no-selection state: picking a role replaces it,
        # and picking it replaces any roles.
        if value == self.ALL:
            return [self.ALL]
        return super().toggled([v for v in values if v != self.ALL], value)

    def apply(
        self, request: HttpRequest, queryset: QuerySet[User], values: list[str]
    ) -> QuerySet[User]:
        # "All roles" beside a role still means every role.
        if self.ALL in values or not may_see_staff_roles(request):
            return queryset
        scoped = cast("OrganisationScopedRequest", request)
        return queryset.filter(
            pk__in=staff_assignments(scoped.organisation)
            .filter(role__in=values)
            .values("user_id")
        )


class AuditActorFilter(TableFilter):
    """Narrows audit entries to one actor, or to the system.

    Choices are the users who acted on the request's organisation. An entry
    whose actor was deleted keeps only a stored name, so it matches "System"
    no more than it matches any user.
    """

    SYSTEM = "system"
    widget = "select"
    multiple = False

    def __init__(self) -> None:
        super().__init__("who", "Who")

    def get_choices(self, request: HttpRequest) -> list[tuple[str, str]]:
        scoped = cast("OrganisationScopedRequest", request)
        actors = User.objects.filter(
            pk__in=AuditLogEntry.objects.filter(
                organisation=scoped.organisation, actor__isnull=False
            ).values("actor_id")
        ).order_by("first_name", "last_name", "email")
        return [
            (self.SYSTEM, "System"),
            *((str(actor.pk), actor.display_name) for actor in actors),
        ]

    def apply(
        self, request: HttpRequest, queryset: QuerySet, values: list[str]
    ) -> QuerySet:
        condition = Q(actor_id__in=[v for v in values if v != self.SYSTEM])
        if self.SYSTEM in values:
            condition |= Q(actor__isnull=True, actor_label="")
        return queryset.filter(condition)


class AuditActionFilter(ChoiceFilter):
    """Narrows audit entries to the chosen actions, offering every registered
    action as a checklist under its group heading."""

    widget = "grouped_checklist"

    def __init__(self) -> None:
        super().__init__("what", "What", lookup="action")

    def get_choices(self, request: HttpRequest) -> list[tuple[str, str]]:
        return [(code, action.label) for code, action in audit_actions().items()]

    def get_groups(
        self, request: HttpRequest
    ) -> list[tuple[str, list[tuple[str, str]]]]:
        return [
            (group, [(action.code, action.label) for action in actions])
            for group, actions in audit_actions_by_group()
        ]
