"""Helpers shared by tests that need a course progress record."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory
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


def age_updated_at(record: CourseProgress) -> datetime:
    """Write an old `updated_at` onto the record past `auto_now`, and return it."""
    past = timezone.now() - timedelta(days=30)
    CourseProgress._base_manager.filter(pk=record.pk).update(updated_at=past)
    return past


def learner_registration_record() -> CourseProgress:
    """A record under an individual registration."""
    record: CourseProgress = CourseProgressFactory()
    return record


def cohort_registration_record() -> CourseProgress:
    """A record under a cohort registration."""
    world = make_move_world()
    _, record = cohort_record(world, world.source, CourseFactory(), percentage=0)
    return record


def inactive_learner_registration_record() -> CourseProgress:
    record: CourseProgress = CourseProgressFactory(
        learner_registration__is_active=False
    )
    return record


def inactive_cohort_registration_record() -> CourseProgress:
    world = make_move_world()
    _, record = cohort_record(
        world, world.source, CourseFactory(), percentage=0, registration_active=False
    )
    return record


def inactive_learner_record() -> CourseProgress:
    record: CourseProgress = CourseProgressFactory(learner__is_active=False)
    return record


def set_updated_at(record: CourseProgress, updated_at: datetime) -> None:
    """Write `updated_at` onto the record past `auto_now`."""
    CourseProgress._base_manager.filter(pk=record.pk).update(updated_at=updated_at)


def resolve_ref(
    document: dict[str, object], schema: dict[str, object]
) -> dict[str, object]:
    """The schema a `$ref` points at in an OpenAPI document, or `schema` itself.

    A `$ref` that drf_spectacular wraps in a one-element `allOf` (to attach
    `readOnly`) is followed too.
    """
    wrapped = cast(list[dict[str, object]], schema.get("allOf", [schema]))
    ref = wrapped[0].get("$ref")
    if ref is None:
        return schema
    target = document
    for part in str(ref).removeprefix("#/").split("/"):
        target = cast(dict[str, object], target[part])
    return target


def query_count(client: APIClient, url: str, headers: dict[str, str]) -> int:
    """The number of queries one GET of `url` runs."""
    with CaptureQueriesContext(connection) as context:
        client.get(url, headers=headers)
    return len(context)


def change_user_email(record: CourseProgress) -> None:
    user = record.learner.user
    user.email = "changed@example.com"
    user.save()


def change_user_first_name(record: CourseProgress) -> None:
    user = record.learner.user
    user.first_name = "Changed"
    user.save()


def change_organisation_name(record: CourseProgress) -> None:
    organisation = record.learner.organisation
    organisation.name = "Changed organisation"
    organisation.save()


def change_course_title(record: CourseProgress) -> None:
    course = record.course
    course.title = "Changed title"
    course.save()
