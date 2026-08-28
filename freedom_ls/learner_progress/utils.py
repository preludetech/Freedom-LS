"""The sync service, plus the percentage it feeds off of.

Home for these mirrors ensure_learner's home in learner_management/utils.py --
there is no services.py convention in this codebase.
"""

from __future__ import annotations

from uuid import UUID

from freedom_ls.content_engine.models import Course
from freedom_ls.learner_management.models import (
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

    bulk_create so a large cohort is one statement, and ignore_conflicts so a
    concurrent individual registration or a re-fired signal loses the race
    harmlessly. bulk_create bypasses save(), so every instance carries its
    site and its grant before the call -- there is no _set_site_from_request
    to fall back on, which is what we want here.
    """
    # No .distinct(): unique_learner_cohort_membership guarantees one
    # membership row per (learner, cohort), so the join cannot duplicate.
    learners = Learner._base_manager.filter(
        cohortmembership__cohort_id=cohort_registration.cohort_id, is_active=True
    )
    CourseProgress._base_manager.bulk_create(
        [
            CourseProgress(
                site_id=learner.site_id,
                learner=learner,
                course_id=cohort_registration.course_id,
                **_registration_kwargs(cohort_registration),
            )
            for learner in learners
        ],
        ignore_conflicts=True,
    )
