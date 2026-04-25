"""Pure read helpers for registration / cohort snapshots.

These helpers stay in ``student_management`` — they walk
``UserCourseRegistration`` and ``CohortMembership`` without importing
``experience_api``. Both domain consumer apps
(``student_interface.xapi_events``, ``student_progress.xapi_events``)
import from here to build the context extensions.
"""

from __future__ import annotations

from django.contrib.sites.models import Site
from django.contrib.sites.requests import RequestSite

from freedom_ls.student_management.models import (
    Cohort,
    CohortMembership,
    UserCourseRegistration,
)


def resolve_user_course_registration(user, course) -> UserCourseRegistration | None:
    """Return a single active registration for ``user`` in ``course`` or None."""
    if user is None or course is None:
        return None
    try:
        reg: UserCourseRegistration = (
            UserCourseRegistration.objects.filter(
                user=user, collection=course, is_active=True
            )
            .select_related("collection")
            .get()
        )
        return reg
    except UserCourseRegistration.DoesNotExist:
        return None
    except UserCourseRegistration.MultipleObjectsReturned:
        # Defensive: should be impossible given the unique constraint.
        fallback: UserCourseRegistration | None = (
            UserCourseRegistration.objects.filter(
                user=user, collection=course, is_active=True
            )
            .order_by("-registered_at")
            .first()
        )
        return fallback


def resolve_cohort_for_user(
    user, site: Site | RequestSite | None = None
) -> Cohort | None:
    """Return the single cohort the user is a member of, or ``None``.

    When the user belongs to zero or multiple cohorts, returns ``None``.
    Callers that need disambiguation can query ``CohortMembership`` directly.
    """
    if user is None:
        return None
    qs = CohortMembership.objects.filter(user=user).select_related("cohort")
    if site is not None and isinstance(site, Site):
        qs = qs.filter(site=site)
    memberships = list(qs[:2])
    if len(memberships) != 1:
        return None
    cohort: Cohort = memberships[0].cohort
    return cohort
