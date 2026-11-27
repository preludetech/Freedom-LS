"""The course filter shared by the educator interface's cohort tables."""

from __future__ import annotations

from typing import cast

from panel_framework.filters import RelatedChoiceFilter

from django.db.models import QuerySet
from django.http import HttpRequest

from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.learner_management.models import CohortCourseRegistration
from freedom_ls.learner_management.queries import courses_visible_to

__all__ = [
    "VisibleCourseFilter",
]


class VisibleCourseFilter(RelatedChoiceFilter):
    """Narrows cohorts to those holding an active registration for a course
    the educator can see."""

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        scoped = cast("OrganisationScopedRequest", request)
        return (
            courses_visible_to(scoped.user, scoped.organisation)
            .prefetch_related("organisations")
            .order_by("title")
        )

    def get_choices(self, request: HttpRequest) -> list[tuple[str, str]]:
        organisation = cast("OrganisationScopedRequest", request).organisation
        return [
            (str(course.pk), course.label_for(organisation, mark_retired=True))
            for course in self.get_queryset(request)
        ]

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
