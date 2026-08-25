from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING
from uuid import UUID

from django.db.models import F, Q

from freedom_ls.form_engine.models import FormProgress, FormStrategy
from freedom_ls.learner_management.queries import learner_for_course
from freedom_ls.learner_progress.models import (
    CourseFormAttempt,
    CourseProgress,
    TopicProgress,
)
from freedom_ls.learner_progress.utils import _registration_kwargs

if TYPE_CHECKING:
    from freedom_ls.accounts.models import User
    from freedom_ls.content_engine.models import Course


def attempt_completes_form(attempt: FormProgress) -> bool:
    """Whether a completed attempt leaves its form finished for progress purposes.

    A learner has to pass to complete: sitting a scored quiz and failing it is an
    attempt, not an item they are done with. A quiz with no pass mark has no bar
    to clear, and neither does a survey, so completing either is enough.
    """
    form = attempt.form
    if form.strategy != FormStrategy.QUIZ or form.quiz_pass_percentage is None:
        return True
    try:
        return attempt.passed()
    except ValueError:
        # An unscored attempt, or a quiz whose questions were added after it was
        # sat, has no percentage to measure against the pass mark.
        return True


def completed_form_item_ids_by_course_progress(
    course_progress_ids: Iterable[UUID] | None = None,
) -> dict[UUID, set[UUID]]:
    """Collection item ids each course progress record counts as having finished.

    Keyed on the placement rather than the form: the same form may be placed
    twice in one course and each placement is sat separately, so a form-keyed
    answer would credit both positions for one sitting. Their latest completed
    attempt decides, matching how the course outline reads a quiz's status and
    how the reports read a learner's score. Pass `course_progress_ids` to
    narrow the scan to the records you care about.

    Attempts whose placement has since been removed are skipped: they name no
    live position in the course, so they can credit none.
    """
    attempts = CourseFormAttempt.objects.filter(
        form_progress__completed_time__isnull=False, collection_item__isnull=False
    ).select_related("form_progress__form")
    if course_progress_ids is not None:
        attempts = attempts.filter(course_progress_id__in=course_progress_ids)

    latest_attempts: dict[tuple[UUID, UUID], FormProgress] = {}
    for attempt in attempts.order_by(
        "form_progress__completed_time", "form_progress__start_time"
    ):
        latest_attempts[(attempt.course_progress_id, attempt.collection_item_id)] = (
            attempt.form_progress
        )

    completed: dict[UUID, set[UUID]] = {}
    for (course_progress_id, collection_item_id), attempt in latest_attempts.items():
        if attempt_completes_form(attempt):
            completed.setdefault(course_progress_id, set()).add(collection_item_id)
    return completed


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
    # wins under (-is_active, -registered_at). Sorting by collection_id first
    # only groups the rows; it does not change which one comes first per course.
    winning_grant: dict[UUID, tuple[str, UUID, UUID]] = {}

    cohort_rows = (
        CohortCourseRegistration.objects.filter(
            collection_id__in=course_ids,
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
        .order_by("collection_id", "-is_active", "-registered_at")
        .values_list("collection_id", "id", "member_learner_id")
    )
    for course_id, registration_id, learner_id in cohort_rows:
        winning_grant.setdefault(
            course_id, (_COHORT_GRANT, registration_id, learner_id)
        )

    individual_rows = (
        LearnerCourseRegistration.objects.filter(
            learner__user=user, collection_id__in=course_ids
        )
        .order_by("collection_id", "-is_active", "-registered_at")
        .values_list("collection_id", "id", "learner_id")
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
