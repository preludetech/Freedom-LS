from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING
from uuid import UUID

from django.db.models import F, Q

from freedom_ls.form_engine.models import FormProgress
from freedom_ls.form_engine.queries import attempt_completes_form
from freedom_ls.learner_management.queries import learner_for_course
from freedom_ls.learner_progress.models import (
    CourseFormAttempt,
    CourseProgress,
    TopicProgress,
)
from freedom_ls.learner_progress.utils import _registration_kwargs

if TYPE_CHECKING:
    from datetime import datetime

    from freedom_ls.accounts.models import User
    from freedom_ls.content_engine.models import Course


def completed_form_item_ids(attempts: Iterable[CourseFormAttempt]) -> set[UUID]:
    """The placements these attempts leave finished.

    The single definition of which sitting decides a placement: the latest
    completed one, ties broken by start. Takes rows rather than running its own
    query, so a caller that has already fetched a record's attempts applies the
    identical rule to them -- reading the same sitting the stored percentage
    reads is the whole point, and a second ordering written out somewhere else
    is how the course outline and the percentage came to disagree before.

    Keyed on the placement rather than the form: the same form may be placed
    twice in one course and each placement is sat separately, so a form-keyed
    answer would credit both positions for one sitting.

    Attempts still open decide nothing -- beginning a retry cannot un-finish
    what an earlier sitting already finished. Neither do attempts whose
    placement has since been removed: they name no live position in the course.
    """
    ranked: list[tuple[tuple[datetime, datetime], UUID, FormProgress]] = []
    for attempt in attempts:
        collection_item_id = attempt.collection_item_id
        form_progress = attempt.form_progress
        completed_time = form_progress.completed_time
        if collection_item_id is None or completed_time is None:
            continue
        ranked.append(
            (
                (completed_time, form_progress.start_time),
                collection_item_id,
                form_progress,
            )
        )

    deciding: dict[UUID, FormProgress] = {}
    for _order, collection_item_id, form_progress in sorted(
        ranked, key=lambda entry: entry[0]
    ):
        deciding[collection_item_id] = form_progress
    return {
        collection_item_id
        for collection_item_id, form_progress in deciding.items()
        if attempt_completes_form(form_progress)
    }


def completed_form_item_ids_by_course_progress(
    course_progress_ids: Iterable[UUID] | None = None,
) -> dict[UUID, set[UUID]]:
    """Collection item ids each course progress record counts as having finished.

    The bulk sibling of `completed_form_item_ids`, which owns the rule; this
    only fetches the rows and groups them by record. Pass `course_progress_ids`
    to narrow the scan to the records you care about. Records that have finished
    nothing are absent from the result rather than mapped to an empty set.
    """
    attempts = CourseFormAttempt.objects.filter(
        form_progress__completed_time__isnull=False, collection_item__isnull=False
    ).select_related("form_progress__form")
    if course_progress_ids is not None:
        attempts = attempts.filter(course_progress_id__in=course_progress_ids)

    by_record: dict[UUID, list[CourseFormAttempt]] = {}
    for attempt in attempts:
        by_record.setdefault(attempt.course_progress_id, []).append(attempt)

    completed = {
        course_progress_id: completed_form_item_ids(rows)
        for course_progress_id, rows in by_record.items()
    }
    return {
        course_progress_id: item_ids
        for course_progress_id, item_ids in completed.items()
        if item_ids
    }


def completed_collection_item_ids(record: CourseProgress) -> set[UUID]:
    """The placements one record has finished, topics and forms together.

    Collection item ids, not topic or form ids: completion is counted by
    position, so a topic placed twice in one course is two placements to finish
    and completing one of them credits one.

    The single definition of "done" for a placement. The stored percentage and
    the finish page's outstanding list both read it, so neither can come to a
    different view of what the learner has left.
    """
    completed = set(
        TopicProgress.objects.filter(
            course_progress=record,
            complete_time__isnull=False,
            collection_item__isnull=False,
        ).values_list("collection_item_id", flat=True)
    )
    return completed | completed_form_item_ids_by_course_progress([record.pk]).get(
        record.pk, set()
    )


def course_progress_for(user: User, course: Course) -> CourseProgress | None:
    """This learner's live record for this course, or None.

    Resolves the registration first and reads the record from it: a learner
    holding both a cohort and an individual registration for one course has
    two records, and the registration order is what says which one the
    learner interface writes to. Every read path starting from a User goes
    through here; filtering CourseProgress by hand is a defect.

    The educator matrix (starts from a Learner and a CohortCourseRegistration
    already), reports (starts from a cohort roster) and
    recalculate_progress_percentages (iterates records directly) are the
    three read paths that legitimately do not go through this.
    """
    resolved = learner_for_course(user, course)
    if resolved is None:
        return None
    return (
        CourseProgress.objects.filter(
            learner=resolved.learner, **_registration_kwargs(resolved.registration)
        )
        # Every caller reaches for .learner or .course -- course_finish's
        # webhook payload reads learner.organisation_id, and the player chrome
        # reads learner.organisation -- so the joins belong here rather than
        # being improvised per call site.
        .select_related("learner__organisation", "course")
        .first()
    )


#: Which grant column each kind of winning registration is stored in, so the
#: bulk resolver's cohort-beats-individual precedence and the column it later
#: reads are declared in one place.
_COHORT_GRANT = "cohort_registration_id"
_INDIVIDUAL_GRANT = "learner_registration_id"


def course_progress_by_course_for(
    user: User, courses: Iterable[Course]
) -> dict[UUID, CourseProgress]:
    """This learner's live record for each of `courses`, keyed by course id.

    The bulk sibling of `course_progress_for`, for the listings that would
    otherwise resolve one course at a time and pay two queries for each. Costs
    three queries whatever the course count: the two registration reads, then
    the records themselves.

    Courses with no registration, or with a registration that has not minted a
    record, are simply absent from the result.
    """
    from freedom_ls.learner_management.models import (
        CohortCourseRegistration,
        LearnerCourseRegistration,
    )

    course_ids = {course.pk for course in courses}
    if not course_ids:
        return {}

    # learner_for_course's order, restated in bulk: a cohort registration beats
    # an individual one, and within each kind the first row seen per course
    # wins under (-is_active, -registered_at). Sorting by course_id first
    # only groups the rows; it does not change which one comes first per course.
    winning_grant: dict[UUID, tuple[str, UUID, UUID]] = {}

    cohort_rows = (
        CohortCourseRegistration.objects.filter(
            course_id__in=course_ids,
            cohort__cohortmembership__learner__user=user,
            cohort__cohortmembership__learner__is_active=True,
            is_active=True,
        )
        # Annotating after the filter reuses the filter's join, so the learner
        # this membership names comes back on the same row rather than costing
        # a lookup per cohort.
        #
        # Unlike learner_for_course, this does not re-read the Learner through
        # the site-aware manager. That re-read exists there only to fall
        # through when a CohortMembership links a Learner in a different
        # organisation than its cohort -- a state CohortMembership.clean()
        # forbids, and organisations are single-site, so a row built through
        # any path that calls full_clean() can't produce it. Assuming clean
        # data here matches every other bulk resolver in this module.
        .annotate(member_learner_id=F("cohort__cohortmembership__learner_id"))
        .order_by("course_id", "-is_active", "-registered_at")
        .values_list("course_id", "id", "member_learner_id")
    )
    for course_id, registration_id, learner_id in cohort_rows:
        winning_grant.setdefault(
            course_id, (_COHORT_GRANT, registration_id, learner_id)
        )

    individual_rows = (
        LearnerCourseRegistration.objects.filter(
            learner__user=user, course_id__in=course_ids
        )
        .order_by("course_id", "-is_active", "-registered_at")
        .values_list("course_id", "id", "learner_id")
    )
    for course_id, registration_id, learner_id in individual_rows:
        winning_grant.setdefault(
            course_id, (_INDIVIDUAL_GRANT, registration_id, learner_id)
        )

    if not winning_grant:
        return {}

    grant_ids: dict[str, list[UUID]] = {_COHORT_GRANT: [], _INDIVIDUAL_GRANT: []}
    winning_learner_ids: set[UUID] = set()
    for grant_field, registration_id, learner_id in winning_grant.values():
        grant_ids[grant_field].append(registration_id)
        winning_learner_ids.add(learner_id)

    # learner_id__in, not just the registration ids: a cohort registration
    # grants a record to every member of the cohort, so without it this
    # hydrates one row per member per course and discards all but one below.
    records = CourseProgress.objects.filter(
        Q(cohort_registration_id__in=grant_ids[_COHORT_GRANT])
        | Q(learner_registration_id__in=grant_ids[_INDIVIDUAL_GRANT]),
        learner_id__in=winning_learner_ids,
    ).select_related("learner", "course")

    by_course: dict[UUID, CourseProgress] = {}
    for record in records:
        grant = winning_grant.get(record.course_id)
        if grant is None:
            continue
        grant_field, registration_id, learner_id = grant
        # A learner holding two grants for one course has two records, and
        # both are in the queryset above; only the winner's may be returned.
        if (
            getattr(record, grant_field) == registration_id
            and record.learner_id == learner_id
        ):
            by_course[record.course_id] = record
    return by_course
