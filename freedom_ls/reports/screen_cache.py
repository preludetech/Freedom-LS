"""A short-lived cache for the gathers that on-screen panels render.

The cached data is permission-neutral: it holds every learner of the cohort,
so callers authorise the request before they read it.

An entry is dropped the moment the cohort's membership or course registrations
change (the receivers in `freedom_ls.reports.signals`), and learners who have
since left the organisation are trimmed on every read. Progress itself waits
for the entry to expire or for an explicit refresh.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from uuid import UUID

from django.core.cache import cache

from freedom_ls.learner_management.models import Cohort, CohortMembership
from freedom_ls.reports.config import config
from freedom_ls.reports.gather import (
    build_progress_data,
    cohort_figures,
    gather_cohort_progress,
    gather_cohort_report_data,
)
from freedom_ls.reports.report_data import (
    CohortProgressData,
    CohortReportData,
    CourseSection,
    ReportTooLargeError,
)

# Bump whenever a cached dataclass changes shape, so a deploy never unpickles
# the old shape into the new code.
SCHEMA_VERSION = 2

KINDS = ("progress", "report")


def _cache_key(site_id: int, cohort_id: UUID, kind: str) -> str:
    return f"reports:screen:{SCHEMA_VERSION}:{site_id}:{cohort_id}:{kind}"


def forget_cohort(site_id: int, cohort_id: UUID) -> None:
    """Drop both of the cohort's entries, so the next read gathers afresh."""
    cache.delete_many([_cache_key(site_id, cohort_id, kind) for kind in KINDS])


def _active_member_ids(cohorts: Sequence[Cohort]) -> dict[UUID, set[UUID]]:
    """Each cohort's learners still active in the organisation, in one query.

    Removed learners keep their membership rows, so every reader that counts
    or lists a cohort's people filters them out here, not by hand.
    """
    by_cohort: dict[UUID, set[UUID]] = {cohort.pk: set() for cohort in cohorts}
    rows = CohortMembership.objects.filter(
        cohort__in=cohorts, learner__is_active=True
    ).values_list("cohort_id", "learner_id")
    for cohort_id, learner_id in rows:
        by_cohort[cohort_id].add(learner_id)
    return by_cohort


@dataclasses.dataclass(frozen=True)
class ProgressGathers:
    """Several cohorts' progress gathers, and the error for each cohort too large to gather."""

    gathered: dict[UUID, CohortProgressData]
    refused: dict[UUID, ReportTooLargeError]


def cached_cohort_progress_many(
    cohorts: Sequence[Cohort], *, refresh: bool = False
) -> ProgressGathers:
    """Each cohort's progress gather, at most REPORTS_SCREEN_CACHE_SECONDS old.

    One cache round trip and one membership query however many cohorts the
    dashboard shows; only a miss costs a gather. A cohort over the size limit
    is reported rather than raised, so one oversized cohort never hides the
    rest.
    """
    keys = {
        cohort.pk: _cache_key(cohort.site_id, cohort.pk, "progress")
        for cohort in cohorts
    }
    found: dict[str, CohortProgressData] = (
        {} if refresh else cache.get_many(list(keys.values()))
    )
    gathered: dict[UUID, CohortProgressData] = {}
    refused: dict[UUID, ReportTooLargeError] = {}
    fresh: dict[str, CohortProgressData] = {}
    for cohort in cohorts:
        data = found.get(keys[cohort.pk])
        if data is None:
            try:
                data = gather_cohort_progress(str(cohort.pk), cohort.site_id)
            except ReportTooLargeError as error:
                refused[cohort.pk] = error
                continue
            fresh[keys[cohort.pk]] = data
        gathered[cohort.pk] = data
    if fresh:
        cache.set_many(fresh, timeout=config.REPORTS_SCREEN_CACHE_SECONDS)
    active_ids = _active_member_ids(
        [cohort for cohort in cohorts if cohort.pk in gathered]
    )
    return ProgressGathers(
        gathered={
            cohort_id: _trim_progress(data, active_ids[cohort_id])
            for cohort_id, data in gathered.items()
        },
        refused=refused,
    )


def cached_cohort_progress(
    cohort: Cohort, *, refresh: bool = False
) -> CohortProgressData:
    """One cohort's progress gather; ReportTooLargeError for an oversized cohort."""
    gathers = cached_cohort_progress_many([cohort], refresh=refresh)
    if cohort.pk in gathers.refused:
        raise gathers.refused[cohort.pk]
    return gathers.gathered[cohort.pk]


def _trim_progress(
    data: CohortProgressData, active_ids: set[UUID]
) -> CohortProgressData:
    remaining = [
        learner for learner in data.learners if learner.learner_id in active_ids
    ]
    if len(remaining) == len(data.learners):
        return data
    return build_progress_data(
        data.cohort_id, data.cohort_name, data.generated_at, remaining
    )


def cached_cohort_report(cohort: Cohort, *, refresh: bool = False) -> CohortReportData:
    """The cohort's report gather without the PDF-only detail, at most REPORTS_SCREEN_CACHE_SECONDS old.

    Removed learners are trimmed on every read, as for the progress gather.
    """
    key = _cache_key(cohort.site_id, cohort.pk, "report")
    data = None if refresh else cache.get(key)
    if data is None:
        # ReportTooLargeError propagates from here and nothing is cached.
        data = gather_cohort_report_data(
            str(cohort.pk), cohort.site_id, pdf_detail=False
        )
        cache.set(key, data, timeout=config.REPORTS_SCREEN_CACHE_SECONDS)
    return _trim_report(data, _active_member_ids([cohort])[cohort.pk])


def _trim_report(data: CohortReportData, active_ids: set[UUID]) -> CohortReportData:
    """Drop rows of learners no longer in the cohort and rebuild every figure that counts them.

    The quiz confusion blocks are left as gathered: they are cohort-wide
    tallies of first attempts, and recounting them needs the answer rows the
    cache never held, so they refresh with the entry.
    """
    learners = [
        learner for learner in data.learners if learner.learner_id in active_ids
    ]
    if len(learners) == len(data.learners):
        return data
    figures = cohort_figures(learners)
    return dataclasses.replace(
        data,
        courses=[_trim_course(section, active_ids) for section in data.courses],
        learners=learners,
        attention_list=figures.attention_list,
        cohort_size=figures.cohort_size,
        median_completion=figures.median_completion,
        not_started_count=figures.not_started_count,
        complete_count=figures.complete_count,
    )


def _trim_course(section: CourseSection, active_ids: set[UUID]) -> CourseSection:
    return dataclasses.replace(
        section,
        learner_rows=[
            row for row in section.learner_rows if row.learner_id in active_ids
        ],
        summary_tables=[
            dataclasses.replace(
                table,
                rows=[row for row in table.rows if row.learner_id in active_ids],
            )
            for table in section.summary_tables
        ],
    )
