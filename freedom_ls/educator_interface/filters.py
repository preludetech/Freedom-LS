"""Table filters specific to the educator interface's lists."""

from __future__ import annotations

from functools import reduce
from operator import or_
from typing import cast

from django.db.models import QuerySet
from django.http import HttpRequest

from freedom_ls.accounts.models import User
from freedom_ls.educator_interface.panels.common.filters import VisibleCourseFilter
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.models import (
    CohortMembership,
    Learner,
)
from freedom_ls.learner_management.queries import (
    STAFF_ROLES,
    VIEW_ORGANISATION_STAFF_ROLES,
    LearnerStatus,
    cohorts_visible_to,
    holds_registration_for_any_expression,
    learner_status_q,
    staff_assignments,
)
from freedom_ls.panel_framework.filters import (
    ChoiceFilter,
    RelatedChoiceFilter,
)
from freedom_ls.role_based_permissions.loader import get_role_config


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
