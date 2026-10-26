"""Table filters specific to the educator interface's lists."""

from __future__ import annotations

from datetime import timedelta
from functools import reduce
from operator import or_
from typing import TYPE_CHECKING, cast

from django.db.models import Q, QuerySet
from django.http import HttpRequest
from django.utils import timezone

from freedom_ls.accounts.models import User
from freedom_ls.audit_log.actions import audit_actions
from freedom_ls.audit_log.models import AuditLogEntry
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
    member_assignments,
)
from freedom_ls.panel_framework.filters import (
    ChoiceFilter,
    RelatedChoiceFilter,
    TableFilter,
)
from freedom_ls.role_based_permissions.loader import get_role_config

if TYPE_CHECKING:
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

    def apply(
        self, request: HttpRequest, queryset: QuerySet, values: list[str]
    ) -> QuerySet:
        return queryset


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
            lookup="",
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


class MemberRoleFilter(ChoiceFilter):
    """Narrows members to those holding a chosen role here; every role while
    the parameter is absent or "All roles" is among the values."""

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

    def apply(
        self, request: HttpRequest, queryset: QuerySet[User], values: list[str]
    ) -> QuerySet[User]:
        # "All roles" beside a role still means every role.
        if self.ALL in values:
            return queryset
        scoped = cast("OrganisationScopedRequest", request)
        return queryset.filter(
            pk__in=member_assignments(scoped.organisation)
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
        super().__init__("who", "Who", lookup="")

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
    action."""

    def __init__(self) -> None:
        super().__init__("what", "What", lookup="action")

    def get_choices(self, request: HttpRequest) -> list[tuple[str, str]]:
        return [(code, action.label) for code, action in audit_actions().items()]


class AuditPeriodFilter(ChoiceFilter):
    """Narrows audit entries to a preset number of calendar days ending
    today, in the project's time zone: "Last 7 days" is today and the six
    days before it."""

    widget = "select"
    multiple = False
    DAYS = {"today": 1, "7d": 7, "30d": 30, "90d": 90, "12m": 365}

    def __init__(self) -> None:
        super().__init__(
            "when",
            "When",
            lookup="created_at",
            choices=[
                ("today", "Today"),
                ("7d", "Last 7 days"),
                ("30d", "Last 30 days"),
                ("90d", "Last 90 days"),
                ("12m", "Last 12 months"),
            ],
        )

    def apply(
        self, request: HttpRequest, queryset: QuerySet, values: list[str]
    ) -> QuerySet:
        midnight = timezone.localtime(timezone.now()).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        start = midnight - timedelta(days=self.DAYS[values[0]] - 1)
        return queryset.filter(created_at__gte=start)
