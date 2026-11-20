"""Table filters specific to the educator interface's lists."""

from __future__ import annotations

from functools import reduce
from operator import or_
from typing import cast

from django.db.models import QuerySet
from django.http import HttpRequest

from freedom_ls.educator_interface.panels.common.filters import VisibleCourseFilter
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.learner_management.models import (
    CohortMembership,
    Learner,
)
from freedom_ls.learner_management.queries import (
    LearnerStatus,
    cohorts_visible_to,
    holds_registration_for_any_expression,
    learner_status_q,
)
from freedom_ls.panel_framework.filters import (
    ChoiceFilter,
    RelatedChoiceFilter,
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
