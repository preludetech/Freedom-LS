"""A short-lived cache for the gathers that on-screen panels render.

The cached data is permission-neutral: it holds every learner of the cohort,
so callers authorise the request before they read it.
"""

from __future__ import annotations

from uuid import UUID

from django.core.cache import cache

from freedom_ls.learner_management.models import Cohort
from freedom_ls.reports.config import config
from freedom_ls.reports.gather import build_progress_data, gather_cohort_progress
from freedom_ls.reports.indexes import load_active_memberships
from freedom_ls.reports.report_data import CohortProgressData

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
