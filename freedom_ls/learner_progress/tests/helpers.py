"""Helpers shared by tests that need a course progress record."""

from __future__ import annotations

from dataclasses import dataclass

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    Learner,
)
from freedom_ls.learner_management.queries import learner_for_course
from freedom_ls.learner_management.tests.helpers import register_user_for_course
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.learner_progress.utils import ensure_course_progress_record


def course_progress_record(
    course: Course, user: User, **fields: object
) -> CourseProgress:
    """The course progress record the player writes into for this learner.

    Registers the user if nothing already grants them the course. The signal
    receivers that would mint the record defer to ``transaction.on_commit``,
    which a rolled-back test transaction never reaches, so this calls the same
    service the player's self-healing path calls.

    Any ``fields`` given are written onto the record, so a test that wants a
    particular percentage or completion time states it here rather than
    building a row the resolver would not pick.
    """
    resolved = learner_for_course(user, course)
    if resolved is None:
        register_user_for_course(course, user)
        resolved = learner_for_course(user, course)
    assert resolved is not None
    record = ensure_course_progress_record(
        resolved.learner, course, resolved.registration
    )
    if fields:
        for name, value in fields.items():
            setattr(record, name, value)
        record.save(update_fields=list(fields))
    return record


@dataclass(frozen=True)
class MoveWorld:
    """A learner in `source`, and a `destination` cohort of the same organisation."""

    learner: Learner
    source: Cohort
    destination: Cohort


def make_move_world() -> MoveWorld:
    source = CohortFactory()
    destination = CohortFactory(organisation=source.organisation)
    learner = LearnerFactory(organisation=source.organisation)
    CohortMembershipFactory(cohort=source, learner=learner)
    return MoveWorld(learner, source, destination)


def cohort_registration(
    cohort: Cohort, course: Course, is_active: bool = True
) -> CohortCourseRegistration:
    registration: CohortCourseRegistration = CohortCourseRegistrationFactory(
        cohort=cohort, course=course, is_active=is_active
    )
    return registration


def cohort_record(
    world: MoveWorld,
    cohort: Cohort,
    course: Course,
    percentage: int,
    registration_active: bool = True,
) -> tuple[CohortCourseRegistration, CourseProgress]:
    """The cohort's registration for the course, and the learner's record under
    it at the given percentage."""
    registration = cohort_registration(cohort, course, registration_active)
    record: CourseProgress = CourseProgressFactory(
        learner=world.learner,
        course=course,
        cohort_registration=registration,
        learner_registration=None,
        progress_percentage=percentage,
    )
    return registration, record
