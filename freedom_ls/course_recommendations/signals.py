"""Signal receivers for the course_recommendations app.

Connected by `CourseRecommendationsConfig.ready()`. A receiver in a module nothing
imports is never connected, and fails silently rather than loudly.

Each receiver deletes the recommendations a save has just made redundant, inside the
caller's transaction, so a registration and the loss of its recommendation commit or
roll back together.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models.signals import post_save
from django.dispatch import receiver

from freedom_ls.course_recommendations.queries import clear_registered_recommendations
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
    LoadedIsActiveMixin,
)

if TYPE_CHECKING:
    from uuid import UUID

    from django.db.models import Model


def _user_of_learner(learner_id: UUID) -> int:
    user_id: int = Learner._base_manager.values_list("user_id", flat=True).get(
        pk=learner_id
    )
    return user_id


def _clear_for_cohort(cohort_id: UUID, site_id: int) -> None:
    users = Learner._base_manager.filter(
        cohortmembership__cohort_id=cohort_id
    ).values_list("user_id", flat=True)
    clear_registered_recommendations(site_id, users)


def _flipped_on(
    instance: LoadedIsActiveMixin, update_fields: frozenset[str] | None
) -> bool:
    """A save that turned is_active on. A save that leaves it out of update_fields
    decides nothing, whatever a stale instance holds."""
    if update_fields is not None and "is_active" not in update_fields:
        return False
    return instance.loaded_is_active is False and instance.is_active


@receiver(post_save, sender=LearnerCourseRegistration)
def clear_on_learner_registration(
    sender: type[Model],
    instance: LearnerCourseRegistration,
    raw: bool = False,
    **kwargs: object,
) -> None:
    """A registration that is active grants the course, so the recommendation is spent."""
    if raw or not instance.is_active:
        return
    clear_registered_recommendations(
        instance.site_id, [_user_of_learner(instance.learner_id)]
    )


@receiver(post_save, sender=CohortCourseRegistration)
def clear_on_cohort_registration(
    sender: type[Model],
    instance: CohortCourseRegistration,
    raw: bool = False,
    **kwargs: object,
) -> None:
    """Every member of a cohort registered for a course is registered for it."""
    if raw or not instance.is_active:
        return
    _clear_for_cohort(instance.cohort_id, instance.site_id)


@receiver(post_save, sender=CohortMembership)
def clear_on_cohort_membership(
    sender: type[Model],
    instance: CohortMembership,
    created: bool,
    raw: bool = False,
    **kwargs: object,
) -> None:
    """Joining a cohort that already holds a course registers the member for it."""
    if raw or not created:
        return
    clear_registered_recommendations(
        instance.site_id, [_user_of_learner(instance.learner_id)]
    )


@receiver(post_save, sender=Cohort)
def clear_on_cohort_reactivation(
    sender: type[Model],
    instance: Cohort,
    raw: bool = False,
    update_fields: frozenset[str] | None = None,
    **kwargs: object,
) -> None:
    """Reactivating a cohort registers its members for the courses it holds again."""
    if raw or not _flipped_on(instance, update_fields):
        return
    _clear_for_cohort(instance.pk, instance.site_id)


@receiver(post_save, sender=Learner)
def clear_on_learner_reactivation(
    sender: type[Model],
    instance: Learner,
    raw: bool = False,
    update_fields: frozenset[str] | None = None,
    **kwargs: object,
) -> None:
    """Reactivating a Learner restores the registrations held through it."""
    if raw or not _flipped_on(instance, update_fields):
        return
    clear_registered_recommendations(instance.site_id, [instance.user_id])
