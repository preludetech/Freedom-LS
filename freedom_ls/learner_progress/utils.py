"""The sync service, plus the percentage it feeds off of.

Home for these mirrors ensure_learner's home in learner_management/utils.py --
there is no services.py convention in this codebase.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from django.db import IntegrityError, transaction

from freedom_ls.content_engine.models import Course
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_progress.models import CourseProgress


def calculate_course_progress_percentage(
    course: Course, completed_collection_item_ids: set[UUID]
) -> int:
    """The share of a course's completable placements one record has finished.

    Counts placements, not content: a topic placed twice in one course is two
    items to complete, and finishing one of them is worth one. Reads the same
    accessor the course outline reads, so the percentage and the outline can
    never disagree about what is done.

    viewable_collection_items() already flattens CourseParts in order and drops
    the part sentinels; the TOPIC/FORM filter drops Activities, which are
    placeable but have no completion to record.
    """
    completable = [
        item
        for item in course.viewable_collection_items()
        if item.child is not None and item.child.content_type in ("TOPIC", "FORM")
    ]
    if not completable:
        return 0

    completed = sum(
        1 for item in completable if item.id in completed_collection_item_ids
    )
    return round((completed / len(completable)) * 100)


def _registration_kwargs(
    registration: LearnerCourseRegistration | CohortCourseRegistration,
) -> dict[str, LearnerCourseRegistration | CohortCourseRegistration]:
    """Which of the two grant FKs this registration fills.

    One helper, so the service's write and course_progress_for's read can
    never disagree about which column a registration lives in.
    """
    if isinstance(registration, LearnerCourseRegistration):
        return {"learner_registration": registration}
    return {"cohort_registration": registration}


def ensure_course_progress_record(
    learner: Learner,
    course: Course,
    registration: LearnerCourseRegistration | CohortCourseRegistration,
) -> CourseProgress:
    """The record for this (registration, learner), created if it is missing.

    Idempotent on the *registration*, not on (learner, course): a learner
    already holding a cohort-granted record who is then registered
    individually gets a second record, because a second grant is a second
    enrolment. An existing record is returned untouched -- no timestamp is
    reset and no grant is re-pointed.

    site comes from learner.site, never from _set_site_from_request: a
    management command, a bulk import or a signal fired under a foreign
    ambient site has no request to read it from. _base_manager for the same
    reason on the lookup half -- SiteAwareManager.get_queryset() would AND a
    foreign ambient site onto it, miss the row that exists, and turn an
    idempotent call into a unique-constraint violation. ensure_learner
    documents the same trap.
    """
    if registration.course_id != course.id:
        raise ValueError(
            "The registration must be for the course passed to "
            "ensure_course_progress_record."
        )
    record, _ = CourseProgress._base_manager.get_or_create(
        learner=learner,
        **_registration_kwargs(registration),
        defaults={"site_id": learner.site_id, "course": course},
    )
    return record


def ensure_course_progress_records_for_cohort_registration(
    cohort_registration: CohortCourseRegistration,
) -> None:
    """One record per current member of the cohort whose Learner is active.

    bulk_create so a large cohort is one statement. Members who already hold a
    record for this registration are excluded up front, so a re-fired signal
    creates nothing; ignore_conflicts is not used because Postgres will not
    apply it to a deferrable unique constraint. A member's own catch-up can
    still mint their record between the exclude and the insert, so a
    conflicting insert falls back to one idempotent create per member.
    bulk_create bypasses save(), so every instance carries its site and its
    grant before the call -- there is no _set_site_from_request to fall back
    on, which is what we want here.
    """
    # No .distinct(): unique_learner_cohort_membership guarantees one
    # membership row per (learner, cohort), so the join cannot duplicate.
    learners = list(
        Learner._base_manager.filter(
            cohortmembership__cohort_id=cohort_registration.cohort_id, is_active=True
        ).exclude(course_progress_records__cohort_registration=cohort_registration)
    )
    try:
        with transaction.atomic():
            CourseProgress._base_manager.bulk_create(
                [
                    CourseProgress(
                        site_id=learner.site_id,
                        learner=learner,
                        course_id=cohort_registration.course_id,
                        **_registration_kwargs(cohort_registration),
                    )
                    for learner in learners
                ]
            )
    except IntegrityError:
        for learner in learners:
            ensure_course_progress_record(
                learner, cohort_registration.course, cohort_registration
            )


@dataclass(frozen=True)
class ProgressCarry:
    """One course both cohorts grant: the learner's record under the source
    registration, the destination registration, and the record already
    there, if any."""

    record: CourseProgress
    destination_registration: CohortCourseRegistration
    existing: CourseProgress | None

    @property
    def continues_at(self) -> int:
        """The percentage the learner keeps: the further of the two records."""
        if self.existing is None:
            return self.record.progress_percentage
        return max(self.record.progress_percentage, self.existing.progress_percentage)


def plan_progress_carry(
    learner: Learner, source: Cohort, destination: Cohort
) -> list[ProgressCarry]:
    """The records a move from `source` to `destination` carries across, by
    course title. Only records under the source's access-granting
    registrations count, and only for courses the destination also grants."""
    destination_registrations = {
        registration.course_id: registration
        for registration in CohortCourseRegistration._base_manager.filter(
            cohort=destination, is_active=True
        )
    }
    source_records = (
        CourseProgress._base_manager.filter(
            learner=learner,
            cohort_registration__cohort=source,
            cohort_registration__is_active=True,
            course_id__in=destination_registrations.keys(),
        )
        .select_related("course", "cohort_registration")
        .order_by("course__title")
    )
    existing_by_registration = {
        record.cohort_registration_id: record
        for record in CourseProgress._base_manager.filter(
            learner=learner,
            cohort_registration__in=destination_registrations.values(),
        ).select_related("course")
    }
    carries: list[ProgressCarry] = []
    for record in source_records:
        target = destination_registrations[record.course_id]
        carries.append(
            ProgressCarry(record, target, existing_by_registration.get(target.pk))
        )
    return carries


@dataclass(frozen=True)
class MoveProgressOutcome:
    course: Course
    progress_percentage: int


def move_progress_preview(
    learner: Learner, source: Cohort, destination: Cohort
) -> list[MoveProgressOutcome]:
    """What will continue for the learner if they move: each shared course
    with the percentage they keep."""
    return [
        MoveProgressOutcome(carry.record.course, carry.continues_at)
        for carry in plan_progress_carry(learner, source, destination)
    ]
