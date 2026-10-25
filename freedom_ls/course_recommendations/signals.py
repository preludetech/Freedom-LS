"""Signal receivers for the course_recommendations app.

Connected by `CourseRecommendationsConfig.ready()`. A receiver in a module nothing
imports is never connected, and fails silently rather than loudly.

Each receiver deletes the recommendations a save has just made redundant, inside the
caller's transaction, so a registration and the loss of its recommendation commit or
roll back together. Only a save that grants a course does the work: a re-save of a
registration that was already active grants nothing new, and would otherwise read
and lock every recommendation of the people it covers.
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
)
from freedom_ls.learner_management.queries import user_id_of_learner

if TYPE_CHECKING:
    from uuid import UUID

    from django.db.models import Model


def _clear_for_cohort(cohort_id: UUID, site_id: int) -> None:
    users = Learner._base_manager.filter(
        cohortmembership__cohort_id=cohort_id
    ).values_list("user_id", flat=True)
    clear_registered_recommendations(site_id, users)


def _granted(
    instance: LearnerCourseRegistration | CohortCourseRegistration,
    created: bool,
    update_fields: frozenset[str] | None,
) -> bool:
    """A registration created active, or turned active, grants its course."""
    return (created and instance.is_active) or instance.flipped_on(update_fields)


@receiver(post_save, sender=LearnerCourseRegistration)
def clear_on_learner_registration(
    sender: type[Model],
    instance: LearnerCourseRegistration,
    created: bool,
    raw: bool = False,
    update_fields: frozenset[str] | None = None,
    **kwargs: object,
) -> None:
    """A registration that becomes active grants the course, so the recommendation is spent."""
    if raw or not _granted(instance, created, update_fields):
        return
    clear_registered_recommendations(
        instance.site_id, [user_id_of_learner(instance.learner_id)]
    )


@receiver(post_save, sender=CohortCourseRegistration)
def clear_on_cohort_registration(
    sender: type[Model],
    instance: CohortCourseRegistration,
    created: bool,
    raw: bool = False,
    update_fields: frozenset[str] | None = None,
    **kwargs: object,
) -> None:
    """Every member of a cohort registered for a course is registered for it."""
    if raw or not _granted(instance, created, update_fields):
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
        instance.site_id, [user_id_of_learner(instance.learner_id)]
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
    if raw or not instance.flipped_on(update_fields):
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
    if raw or not instance.flipped_on(update_fields):
        return
    clear_registered_recommendations(instance.site_id, [instance.user_id])
