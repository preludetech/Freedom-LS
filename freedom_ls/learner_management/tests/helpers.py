"""Helpers shared by tests that need a registered learner."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from django.contrib.auth.models import AnonymousUser

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course, CourseAudience
from freedom_ls.learner_management.factories import (
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.tests.site_context import site_context

type AudienceCase = tuple[User | AnonymousUser, Course]


def register_user_for_course(course: Course, user: User | None = None) -> User:
    """Register a user (creating one if not given) for `course`; return the user."""
    resolved_user: User = UserFactory() if user is None else user
    learner = LearnerFactory(user=resolved_user)
    LearnerCourseRegistrationFactory(learner=learner, course=course, is_active=True)
    return resolved_user


def _course(audience: CourseAudience) -> Course:
    return cast(Course, CourseFactory(audience=audience))


def _user() -> User:
    return cast(User, UserFactory())


def _learner_user(**kwargs: object) -> User:
    return cast(User, LearnerFactory(**kwargs).user)


def _organisation_course(audience: CourseAudience) -> tuple[Course, Organisation]:
    organisation = cast(Organisation, OrganisationFactory())
    course = _course(audience)
    course.organisations.add(organisation)
    return course, organisation


def _course_of_no_organisation() -> AudienceCase:
    return _user(), _course(CourseAudience.ORGANISATION_LEARNERS)


def _learner_in_organisation() -> AudienceCase:
    course, organisation = _organisation_course(CourseAudience.ORGANISATION_LEARNERS)
    return _learner_user(organisation=organisation), course


def _learner_of_another_organisation() -> AudienceCase:
    course, _ = _organisation_course(CourseAudience.ORGANISATION_LEARNERS)
    return _learner_user(), course


def _removed_learner() -> AudienceCase:
    course, organisation = _organisation_course(CourseAudience.ORGANISATION_LEARNERS)
    return _learner_user(organisation=organisation, is_active=False), course


def _anonymous_on_organisation_course() -> AudienceCase:
    course, _ = _organisation_course(CourseAudience.ORGANISATION_LEARNERS)
    return AnonymousUser(), course


def _registered_outsider() -> AudienceCase:
    course, _ = _organisation_course(CourseAudience.ORGANISATION_LEARNERS)
    return register_user_for_course(course), course


def _user_without_learner_on_public_course() -> AudienceCase:
    course, _ = _organisation_course(CourseAudience.PUBLIC)
    return _user(), course


def _anonymous_on_public_course() -> AudienceCase:
    course, _ = _organisation_course(CourseAudience.PUBLIC)
    return AnonymousUser(), course


def _learner_of_the_course_organisation_on_another_site() -> AudienceCase:
    other_site = SiteFactory()
    with site_context(other_site):
        course, organisation = _organisation_course(
            CourseAudience.ORGANISATION_LEARNERS
        )
        user = _learner_user(organisation=organisation)
    return user, course


#: Each audience scenario as (builder, whether the user is in the audience).
#: Builders run under mock_site_context and return the user and the course.
AUDIENCE_CASES: dict[str, tuple[Callable[[], AudienceCase], bool]] = {
    "not_an_organisation_course": (_course_of_no_organisation, True),
    "learner_in_organisation": (_learner_in_organisation, True),
    "learner_of_another_organisation": (_learner_of_another_organisation, False),
    "removed_learner": (_removed_learner, False),
    "anonymous_on_organisation_course": (_anonymous_on_organisation_course, False),
    "registered_outsider": (_registered_outsider, True),
    "user_without_learner_on_public_course": (
        _user_without_learner_on_public_course,
        True,
    ),
    "anonymous_on_public_course": (_anonymous_on_public_course, True),
    "learner_on_another_site": (
        _learner_of_the_course_organisation_on_another_site,
        False,
    ),
}
