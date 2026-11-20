"""The dashboard's figures, their gather and the lazy panel that renders them."""

from __future__ import annotations

import dataclasses
import statistics
from collections import defaultdict
from datetime import datetime
from functools import cached_property
from typing import cast
from uuid import UUID

from django.db.models import Count, Prefetch, QuerySet

from freedom_ls.educator_interface.avatars import learner_avatars
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.learner_management.capabilities import can
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
)
from freedom_ls.learner_management.queries import (
    cohort_learner_count,
    cohorts_visible_to,
)
from freedom_ls.panel_framework.lazy_panels import LazyBodyPanel
from freedom_ls.reports.config import config as reports_config
from freedom_ls.reports.report_data import (
    ATTENTION_LIST_MAX,
    AtRiskFlag,
    CohortProgressData,
    over_limit_message,
)
from freedom_ls.reports.screen_cache import cached_cohort_progress_many

__all__ = [
    "CohortFlags",
    "CohortGather",
    "CohortProgressRow",
    "DashboardPanel",
    "ExcludedCohort",
    "FlaggedLearnerRow",
    "GatheredFigures",
    "InlineFigures",
    "_average_progress",
    "_cohort_rows",
    "_flagged_learner_rows",
    "_gather_visible",
    "gathered_figures",
    "inline_figures",
    "visible_active_cohorts",
]


@dataclasses.dataclass(frozen=True)
class InlineFigures:
    """The two dashboard tiles that need no gather."""

    learner_count: int
    cohort_count: int


@dataclasses.dataclass(frozen=True)
class CohortFlags:
    """One cohort's view of a flagged learner."""

    cohort: Cohort
    completion_percentage: int
    flags: list[AtRiskFlag]


@dataclasses.dataclass(frozen=True)
class FlaggedLearnerRow:
    """A learner flagged in at least one visible cohort, with each cohort's detail."""

    learner_id: UUID
    full_name: str
    sort_key: tuple[str, str]
    lowest_completion: int
    cohorts: list[CohortFlags]


@dataclasses.dataclass(frozen=True)
class CohortProgressRow:
    cohort: Cohort
    mean_completion: int | None
    learner_count: int
    flagged_count: int


@dataclasses.dataclass(frozen=True)
class ExcludedCohort:
    """A visible cohort over the report size limit, left out of the gathered figures."""

    cohort: Cohort
    learner_count: int

    @property
    def message(self) -> str:
        return over_limit_message(
            self.cohort.name, self.learner_count, reports_config.REPORTS_MAX_LEARNERS
        )


@dataclasses.dataclass(frozen=True)
class GatheredFigures:
    average_progress: int | None
    # Distinct flagged learners, not capped to the rows shown.
    attention_count: int
    # The first ATTENTION_LIST_MAX by lowest completion.
    attention_rows: list[FlaggedLearnerRow]
    cohort_rows: list[CohortProgressRow]
    excluded: list[ExcludedCohort]
    # The oldest gather behind the figures; None when no cohort was gathered.
    figures_as_of: datetime | None


type CohortGather = tuple[Cohort, CohortProgressData]


def visible_active_cohorts(request: OrganisationScopedRequest) -> QuerySet[Cohort]:
    """The active cohorts the user may see, which scope every dashboard figure.

    Each cohort's active course registrations come along, so an attention row
    can name the courses a flagged cohort is registered for without a query
    per row.
    """
    return (
        cohorts_visible_to(request.user, request.organisation)
        .filter(is_active=True)
        .prefetch_related(
            Prefetch(
                "course_registrations",
                queryset=CohortCourseRegistration.objects.filter(is_active=True)
                .select_related("course")
                .prefetch_related("course__organisations"),
            )
        )
        .order_by("name")
    )


def inline_figures(cohorts: list[Cohort]) -> InlineFigures:
    learners = CohortMembership.objects.filter(
        cohort__in=cohorts, learner__is_active=True
    ).aggregate(n=Count("learner_id", distinct=True))["n"]
    return InlineFigures(learner_count=learners, cohort_count=len(cohorts))


def _gather_visible(
    cohorts: list[Cohort],
) -> tuple[list[CohortGather], list[ExcludedCohort]]:
    gathers = cached_cohort_progress_many(cohorts)
    return (
        [
            (cohort, gathers.gathered[cohort.pk])
            for cohort in cohorts
            if cohort.pk in gathers.gathered
        ],
        [
            ExcludedCohort(cohort, cohort_learner_count(cohort))
            for cohort in cohorts
            if cohort.pk in gathers.refused
        ],
    )


def _average_progress(gathers: list[CohortGather]) -> int | None:
    """Each learner once, at the mean of their completion across the cohorts gathered."""
    completions: dict[UUID, list[int]] = defaultdict(list)
    for _cohort, data in gathers:
        for learner in data.learners:
            completions[learner.learner_id].append(learner.completion_percentage)
    if not completions:
        return None
    return round(
        statistics.fmean(statistics.fmean(values) for values in completions.values())
    )


def _flagged_learner_rows(gathers: list[CohortGather]) -> list[FlaggedLearnerRow]:
    by_learner: dict[UUID, FlaggedLearnerRow] = {}
    for cohort, data in gathers:
        for learner in data.learners:
            if not learner.flags:
                continue
            entry = CohortFlags(cohort, learner.completion_percentage, learner.flags)
            row = by_learner.get(learner.learner_id)
            by_learner[learner.learner_id] = (
                FlaggedLearnerRow(
                    learner.learner_id,
                    learner.full_name,
                    learner.sort_key,
                    learner.completion_percentage,
                    [entry],
                )
                if row is None
                else dataclasses.replace(
                    row,
                    lowest_completion=min(
                        row.lowest_completion, learner.completion_percentage
                    ),
                    cohorts=[*row.cohorts, entry],
                )
            )
    return sorted(
        by_learner.values(), key=lambda row: (row.lowest_completion, row.sort_key)
    )


def _cohort_rows(gathers: list[CohortGather]) -> list[CohortProgressRow]:
    rows = [
        CohortProgressRow(
            cohort,
            data.mean_completion,
            data.cohort_size,
            sum(1 for learner in data.learners if learner.flags),
        )
        for cohort, data in gathers
    ]
    # An empty cohort has no mean, so it sorts after every cohort that has one.
    return sorted(
        rows,
        key=lambda row: (
            row.mean_completion is None,
            row.mean_completion or 0,
            row.cohort.name,
        ),
    )


def gathered_figures(cohorts: list[Cohort]) -> GatheredFigures:
    """The dashboard figures that need each cohort's progress gather."""
    gathers, excluded = _gather_visible(cohorts)
    flagged = _flagged_learner_rows(gathers)
    return GatheredFigures(
        average_progress=_average_progress(gathers),
        attention_count=len(flagged),
        attention_rows=flagged[:ATTENTION_LIST_MAX],
        cohort_rows=_cohort_rows(gathers),
        excluded=excluded,
        figures_as_of=min(
            (data.generated_at for _cohort, data in gathers), default=None
        ),
    )


class DashboardPanel(LazyBodyPanel):
    """The organisation dashboard: the inline tiles at once, the gathered figures lazily."""

    title = "Reporting"
    load_label = "Load the figures"
    template_name = "educator_interface/panels/dashboard.html"
    region_template_name = "educator_interface/panels/dashboard_region.html"
    skeleton_shape = "row"

    @cached_property
    def visible_cohorts(self) -> list[Cohort]:
        # Evaluated once per request: the empty check, the inline tiles and the
        # gathered figures all read the same list.
        return list(
            visible_active_cohorts(cast("OrganisationScopedRequest", self.request))
        )

    def get_context_data(self) -> dict[str, object]:
        request = cast("OrganisationScopedRequest", self.request)
        cohorts = self.visible_cohorts
        context = super().get_context_data()
        context.update(
            cohorts=cohorts,
            inline=inline_figures(cohorts),
            # An organisation admin can create cohorts; a cohort-scoped role cannot.
            is_organisation_admin=can(
                request.user,
                "freedom_ls_learner_management.change_cohort",
                request.organisation,
            ),
        )
        return context

    def get_loaded_context(self) -> dict[str, object]:
        figures = gathered_figures(self.visible_cohorts)
        return {
            "figures": figures,
            "avatars": learner_avatars(
                row.learner_id for row in figures.attention_rows
            ),
        }
