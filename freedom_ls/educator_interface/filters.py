"""Table filters specific to the educator interface's lists."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from django.db.models import QuerySet
from django.http import HttpRequest

from freedom_ls.learner_management.models import CohortCourseRegistration
from freedom_ls.learner_management.queries import courses_visible_to
from freedom_ls.panel_framework.filters import RelatedChoiceFilter, TableFilter

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
