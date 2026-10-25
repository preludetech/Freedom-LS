"""Query helpers for course_recommendations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.db import transaction

from freedom_ls.course_recommendations.models import RecommendedCourse
from freedom_ls.learner_management.queries import registered_course_pairs

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
    from django.db.models import QuerySet

    from freedom_ls.accounts.models import User

    type RequestUser = User | AnonymousUser | AbstractBaseUser


def get_recommended_courses(user: RequestUser) -> QuerySet[RecommendedCourse]:
    """Get recommended courses for a user. Returns empty queryset for anonymous users."""
    if not user.is_authenticated:
        return RecommendedCourse.objects.none()
    return RecommendedCourse.objects.filter(user=user).select_related("course")


def lock_users(site_id: int, user_ids: Iterable[int]) -> None:
    """Lock these users' rows, in pk order, for the rest of the current transaction.

    Whether a user should hold a recommendation depends on their registrations,
    and a registration being saved and a rule run deciding to recommend cannot
    see each other's uncommitted rows. Both take this lock before they read the
    registrations, so whichever comes second reads the first one's commit. The
    user row is the one row both sides share that already exists.
    """
    list(
        get_user_model()
        ._base_manager.select_for_update(no_key=True)
        .filter(site_id=site_id, pk__in=list(user_ids))
        .order_by("pk")
        .values_list("pk", flat=True)
    )


def clear_registered_recommendations(site_id: int, user_ids: Iterable[int]) -> int:
    """Delete these users' recommendations for courses they are registered for, whoever made them.

    The users are locked before the registrations are read, so a rule run for
    the same user is serialised against this clear (see lock_users). The
    recommendations are then locked in pk order: a rule evaluation re-reads a
    recommendation under the same lock before attaching itself to it, so
    neither side commits a provenance row that points at a deleted recommendation.
    """
    ids = list(user_ids)
    with transaction.atomic():
        lock_users(site_id, ids)
        registered = registered_course_pairs(site_id, ids)
        if not registered:
            return 0
        locked = (
            RecommendedCourse._base_manager.select_for_update(no_key=True)
            .filter(
                site_id=site_id,
                user_id__in=ids,
                course_id__in={course for _, course in registered},
            )
            .order_by("pk")
            .values_list("pk", "user_id", "course_id")
        )
        stale = [
            pk
            for pk, user_id, course_id in locked
            if (user_id, course_id) in registered
        ]
        if stale:
            RecommendedCourse._base_manager.filter(pk__in=stale).delete()
        return len(stale)
