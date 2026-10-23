"""A short-lived cache for the gathers that on-screen panels render.

The cached data is permission-neutral: it holds every learner of the cohort,
so callers authorise the request before they read it.
"""

from __future__ import annotations

import dataclasses
from uuid import UUID

from django.core.cache import cache

from freedom_ls.learner_management.models import Cohort
from freedom_ls.reports.config import config
from freedom_ls.reports.gather import (
    _build_attention_list,
    _completion_statistics,
    build_progress_data,
    gather_cohort_progress,
    gather_cohort_report_data,
)
from freedom_ls.reports.indexes import load_active_memberships
from freedom_ls.reports.report_data import (
    CohortProgressData,
    CohortReportData,
    CourseSection,
)

# Bump whenever a cached dataclass changes shape, so a deploy never unpickles
# the old shape into the new code.
SCHEMA_VERSION = 1


def _cache_key(site_id: int, cohort_id: UUID, kind: str) -> str:
    return f"reports:screen:{SCHEMA_VERSION}:{site_id}:{cohort_id}:{kind}"


def _active_member_ids(cohort: Cohort) -> set[UUID]:
    return set(
        load_active_memberships(cohort, cohort.site_id).values_list(
            "learner_id", flat=True
        )
    )


def cached_cohort_progress(
    cohort: Cohort, *, refresh: bool = False
) -> CohortProgressData:
    """The cohort's progress gather, at most REPORTS_SCREEN_CACHE_SECONDS old.

    Learners removed since the gather ran are dropped on every read and the
    figures rebuilt, so a removal shows at once while the gather itself waits
    for expiry. The cached data is permission-neutral: callers authorise first.
    """
    key = _cache_key(cohort.site_id, cohort.pk, "progress")
    data = None if refresh else cache.get(key)
    if data is None:
        # ReportTooLargeError propagates from here and nothing is cached.
        data = gather_cohort_progress(str(cohort.pk), cohort.site_id)
        cache.set(key, data, timeout=config.REPORTS_SCREEN_CACHE_SECONDS)
    return _trim_progress(data, _active_member_ids(cohort))


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
    """The cohort's report gather, at most REPORTS_SCREEN_CACHE_SECONDS old.

    Removed learners are trimmed on every read, as for the progress gather.
    The cached data is permission-neutral: callers authorise first.
    """
    key = _cache_key(cohort.site_id, cohort.pk, "report")
    data = None if refresh else cache.get(key)
    if data is None:
        # ReportTooLargeError propagates from here and nothing is cached.
        data = gather_cohort_report_data(str(cohort.pk), cohort.site_id)
        cache.set(key, data, timeout=config.REPORTS_SCREEN_CACHE_SECONDS)
    return _trim_report(data, _active_member_ids(cohort))


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
    stats = _completion_statistics(
        [learner.completion_percentage for learner in learners]
    )
    return dataclasses.replace(
        data,
        courses=[_trim_course(section, active_ids) for section in data.courses],
        learners=learners,
        attention_list=_build_attention_list(learners),
        cohort_size=len(learners),
        median_completion=stats.median_completion,
        not_started_count=stats.not_started_count,
        complete_count=stats.complete_count,
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
