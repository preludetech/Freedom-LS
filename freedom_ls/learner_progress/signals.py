"""Signal receivers for the learner_progress app.

Connected by `LearnerProgressConfig.ready()`. A receiver in a module nothing imports
is never connected, and fails silently rather than loudly.

`TopicProgress` completion is recalculated off `post_save`, naming its sender
explicitly — a new concrete `CourseItemProgress` subclass does not inherit the
behaviour the way it would from a `save()` override, it needs its own `@receiver`
line here. Form completions arrive instead on `form_attempt_completed`, which
`form_engine` sends for every attempt, course-bound or not.
"""

from __future__ import annotations

from typing import cast

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from freedom_ls.form_engine.models import FormProgress
from freedom_ls.form_engine.signals import form_attempt_completed
from freedom_ls.learner_management.models import (
    CohortCourseRegistration,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.utils import calculate_course_progress_percentage
from freedom_ls.learner_progress.models import (
    CourseFormAttempt,
    CourseItemProgress,
    CourseProgress,
    TopicProgress,
)
from freedom_ls.learner_progress.queries import (
    completed_collection_item_ids,
)
from freedom_ls.learner_progress.utils import (
    ensure_course_progress_record,
    ensure_course_progress_records_for_cohort_registration,
)


def recalculate_progress_percentage(record: CourseProgress) -> None:
    """Rewrite one record's stored percentage from its own completion rows.

    The escape hatch for code that writes completions without a transition to
    fire — see `recalculate_course_progress_on_save`.

    `update_fields`, because `last_accessed_time` is written by the player: a
    background recalculation must not look like a visit.
    """
    record.progress_percentage = calculate_course_progress_percentage(
        record.course, completed_collection_item_ids(record)
    )
    record.save(update_fields=["progress_percentage"])


def update_course_progress_on_completion(item_progress: CourseItemProgress) -> None:
    """Recalculate the record's percentage after one of its items completes."""
    recalculate_progress_percentage(
        cast("CourseProgress", item_progress.course_progress)
    )


@receiver(post_save, sender=TopicProgress)
def recalculate_course_progress_on_save(
    sender: type[CourseItemProgress],
    instance: CourseItemProgress,
    raw: bool = False,
    **kwargs: object,
) -> None:
    """Recalculate the record's percentage when a save completes a topic or form.

    Only a save fires this — `queryset.update()`, `bulk_create()` and
    `bulk_update()` write rows without it, and neither does a row created with
    its completion time already set. Code that completes items in bulk has to
    call `recalculate_progress_percentage()` for the affected records itself.

    `raw` saves come from `loaddata`, which writes exactly the rows in the fixture:
    recomputing a percentage from a fixture load would overwrite the one the
    fixture author asked for.
    """
    if raw:
        return

    content_item = instance.newly_completed_item()
    if content_item is None:
        return

    update_course_progress_on_completion(instance)
    instance.mark_completion_recorded()


@receiver(
    form_attempt_completed, dispatch_uid="learner_progress.form_attempt_completed"
)
def recalculate_course_progress_on_form_attempt(
    sender: type[FormProgress],
    attempt: FormProgress,
    **kwargs: object,
) -> None:
    """Recalculate the record's percentage when an attempt inside it completes.

    An attempt sat outside a course -- a standalone survey, an application form
    -- has no `CourseFormAttempt`, and there is no percentage anywhere for it to
    move. That is the whole reason the attempt layer lives in `form_engine`:
    completing one costs a single indexed lookup here and touches nothing else.
    """
    course_attempt = (
        CourseFormAttempt.objects.filter(form_progress=attempt)
        .select_related("course_progress__course")
        .first()
    )
    if course_attempt is None:
        return

    recalculate_progress_percentage(course_attempt.course_progress)


def _ensure_and_announce(
    registration: LearnerCourseRegistration, *, announce: bool
) -> None:
    """Mint this registration's record, then announce it to integrators.

    `announce` is decided when the signal is received, not here: by the time
    the transaction commits, `created` is long gone.

    _base_manager on the Learner lookup, because this runs from anywhere a
    registration is written -- a management command with no ambient request,
    or a request whose ambient site is not the learner's own.
    """
    from freedom_ls.webhooks.events import fire_webhook_event

    learner = Learner._base_manager.select_related("user").get(
        pk=registration.learner_id
    )
    record = ensure_course_progress_record(learner, registration.course, registration)
    if not announce:
        return

    fire_webhook_event(
        "course.registered",
        {
            "user_id": learner.user_id,
            "user_email": learner.user.email,
            "course_id": str(registration.course_id),
            "course_title": registration.course.title,
            "registered_at": registration.registered_at.isoformat(),
            "organisation_id": str(learner.organisation_id),
            "course_progress_id": str(record.id),
        },
    )


def _ensure_for_membership(membership: CohortMembership) -> None:
    """One record per course the new member's cohort is currently registered for."""
    learner = membership.learner
    if not learner.is_active:
        return
    registrations = CohortCourseRegistration._base_manager.filter(
        cohort_id=membership.cohort_id, is_active=True
    ).select_related("course")
    for registration in registrations:
        ensure_course_progress_record(learner, registration.course, registration)


# Registration is what grants a record, so these three receivers are the only
# place records are minted. There is deliberately no post_delete counterpart:
# removing a membership, withdrawing a registration and deactivating a learner
# are access decisions, and none of them retires work already recorded.
#
# on_commit throughout, for two reasons. A cohort fan-out half-visible to a
# concurrent reader before the registration itself commits would be worse than
# no fan-out at all; and deferring is what lets course.registered be announced
# only once the record it names exists.


@receiver(post_save, sender=LearnerCourseRegistration)
def ensure_course_progress_on_learner_registration(
    sender: type[LearnerCourseRegistration],
    instance: LearnerCourseRegistration,
    created: bool,
    raw: bool = False,
    **kwargs: object,
) -> None:
    """Mint the record an individual registration grants, and announce it."""
    if raw:
        # loaddata: deriving records from a fixture would invent data the
        # fixture author did not ask for.
        return
    if not instance.is_active:
        # A withdrawn registration grants nothing: not on a deactivating save,
        # and not on a creation either -- an import of a past enrolment would
        # otherwise announce one that was never active.
        return
    transaction.on_commit(lambda: _ensure_and_announce(instance, announce=created))


@receiver(post_save, sender=CohortCourseRegistration)
def ensure_course_progress_on_cohort_registration(
    sender: type[CohortCourseRegistration],
    instance: CohortCourseRegistration,
    raw: bool = False,
    **kwargs: object,
) -> None:
    """Fan a cohort registration out to a record per active member."""
    if raw or not instance.is_active:
        return
    transaction.on_commit(
        lambda: ensure_course_progress_records_for_cohort_registration(instance)
    )


@receiver(post_save, sender=CohortMembership)
def ensure_course_progress_on_cohort_membership(
    sender: type[CohortMembership],
    instance: CohortMembership,
    raw: bool = False,
    **kwargs: object,
) -> None:
    """Catch a learner up on whatever their new cohort is already registered for."""
    if raw:
        return
    transaction.on_commit(lambda: _ensure_for_membership(instance))
