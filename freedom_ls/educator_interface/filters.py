"""Table filters specific to the educator interface's lists."""

from __future__ import annotations

from functools import reduce
from operator import or_
from typing import TYPE_CHECKING, cast

from django.db.models import QuerySet
from django.http import HttpRequest

from freedom_ls.learner_management.models import (
    CohortCourseRegistration,
    CohortMembership,
    Learner,
)
from freedom_ls.learner_management.queries import (
    MEMBER_ROLES,
    LearnerStatus,
    cohorts_visible_to,
    courses_visible_to,
    holds_registration_for_any_expression,
    learner_status_q,
)
from freedom_ls.panel_framework.filters import (
    ChoiceFilter,
    RelatedChoiceFilter,
    TableFilter,
)
from freedom_ls.role_based_permissions.loader import get_role_config

if TYPE_CHECKING:
    from freedom_ls.accounts.models import User
    from freedom_ls.educator_interface.views import OrganisationScopedRequest


class ShowInactiveFilter(TableFilter):
    """A toggle that widens a list to include inactive rows.

    The table, not this filter, does the work: a filter can only narrow the
    queryset it is given, so the table stops excluding inactive rows when this
    toggle is set.
    """

    def __init__(self, key: str, label: str) -> None:
        super().__init__(key, label, lookup="")

    def get_choices(self, request: HttpRequest) -> list[tuple[str, str]]:
        return [("1", self.label)]

    def apply(self, queryset: QuerySet, values: list[str]) -> QuerySet:
        return queryset


class VisibleCourseFilter(RelatedChoiceFilter):
    """Narrows cohorts to those holding an active registration for a course
    the educator can see."""

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        scoped = cast("OrganisationScopedRequest", request)
        return courses_visible_to(scoped.user, scoped.organisation).order_by("title")

    def apply(self, queryset: QuerySet, values: list[str]) -> QuerySet:
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
            lookup="",
            choices=LearnerStatus.choices,
            default=(LearnerStatus.ACTIVE, LearnerStatus.PENDING),
            always_shown=True,
        )

    def apply(
        self, queryset: QuerySet[Learner], values: list[str]
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
        self, queryset: QuerySet[Learner], values: list[str]
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
        self, queryset: QuerySet[Learner], values: list[str]
    ) -> QuerySet[Learner]:
        return queryset.filter(holds_registration_for_any_expression(None, values))


class MemberRoleFilter(ChoiceFilter):
    """Narrows members to those holding a chosen role here; every role while
    the parameter is absent or "All roles" is among the values.

    The table does the narrowing: apply() has no request, and the
    organisation is only known there. The same split holds for
    ShowInactiveFilter and the cohort table.
    """

    ALL = "all"
    widget = "select"

    def __init__(self) -> None:
        super().__init__(
            "role", "Role", lookup="", default=(self.ALL,), always_shown=True
        )

    def get_choices(self, request: HttpRequest) -> list[tuple[str, str]]:
        scoped = cast("OrganisationScopedRequest", request)
        config = get_role_config(scoped.organisation.site.name)
        return [
            (self.ALL, "All roles"),
            *((role, config[role].display_name) for role in MEMBER_ROLES),
        ]

    def toggled(self, values: list[str], value: str) -> list[str]:
        # "All roles" is the no-selection state: picking a role replaces it,
        # and picking it replaces any roles.
        if value == self.ALL:
            return [self.ALL]
        return super().toggled([v for v in values if v != self.ALL], value)

    def apply(self, queryset: QuerySet[User], values: list[str]) -> QuerySet[User]:
        return queryset
