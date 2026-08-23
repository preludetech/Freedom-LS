"""Tests for learner_management.utils.is_registered_for_course and its
queryset-level mirror, learner_management.queries.is_registered_for_course_expression.

Both functions answer the same question -- direct registration or cohort
registration, gated on an active Learner. One gates the player, the other
gates catalogue listings, and a learner must never see a course in one and be
refused by the other, so every scenario they share is asserted through both
at once via ``_assert_both_agree``. Only the cases one function has and the
other does not get their own test.
"""

from __future__ import annotations

import uuid
from typing import cast

import pytest

from django.contrib.auth.models import AnonymousUser

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Cohort, Learner
from freedom_ls.learner_management.queries import is_registered_for_course_expression
from freedom_ls.learner_management.utils import is_registered_for_course


def _register_via_cohort(learner: Learner, course: Course) -> Cohort:
    """Put ``learner`` in a new cohort and register that cohort for ``course``.
    Returns the cohort so a caller can add a second member to it."""
    cohort = cast(
        Cohort,
        CohortFactory(organisation=learner.organisation, name=f"Cohort {uuid.uuid4()}"),
    )
    CohortMembershipFactory(learner=learner, cohort=cohort)
    CohortCourseRegistrationFactory(cohort=cohort, collection=course, is_active=True)
    return cohort


def _expression_result(user: User, course: Course) -> bool:
    """Evaluate is_registered_for_course_expression for one course."""
    return bool(
        Course.objects.filter(pk=course.pk)
        .annotate(_registered=is_registered_for_course_expression(user))
        .get()
        ._registered
    )


def _assert_both_agree(user: User, course: Course, *, expected: bool) -> None:
    assert is_registered_for_course(user, course) is expected
    assert _expression_result(user, course) is expected


@pytest.mark.django_db
class TestDirectRegistration:
    def test_active_registration_held_by_an_active_learner_grants_access(
        self, mock_site_context
    ):
        course = CourseFactory()
        learner = LearnerFactory()
        LearnerCourseRegistrationFactory(
            learner=learner, collection=course, is_active=True
        )

        _assert_both_agree(learner.user, course, expected=True)

    def test_inactive_registration_grants_nothing(self, mock_site_context):
        course = CourseFactory()
        learner = LearnerFactory()
        LearnerCourseRegistrationFactory(
            learner=learner, collection=course, is_active=False
        )

        _assert_both_agree(learner.user, course, expected=False)

    def test_removed_learner_grants_nothing_though_registration_is_active(
        self, mock_site_context
    ):
        """An active registration held by a removed Learner grants nothing:
        records are preserved, but access is suspended."""
        course = CourseFactory()
        learner = LearnerFactory(is_active=False)
        LearnerCourseRegistrationFactory(
            learner=learner, collection=course, is_active=True
        )

        _assert_both_agree(learner.user, course, expected=False)

    def test_reactivating_a_removed_learner_restores_access(self, mock_site_context):
        course = CourseFactory()
        learner = LearnerFactory(is_active=False)
        LearnerCourseRegistrationFactory(
            learner=learner, collection=course, is_active=True
        )

        learner.is_active = True
        learner.save()

        _assert_both_agree(learner.user, course, expected=True)


@pytest.mark.django_db
class TestCohortRegistration:
    def test_active_cohort_registration_grants_access(self, mock_site_context):
        course = CourseFactory()
        learner = LearnerFactory()
        _register_via_cohort(learner, course)

        _assert_both_agree(learner.user, course, expected=True)

    def test_removed_learner_grants_nothing_through_a_cohort(self, mock_site_context):
        course = CourseFactory()
        learner = LearnerFactory(is_active=False)
        _register_via_cohort(learner, course)

        _assert_both_agree(learner.user, course, expected=False)

    def test_a_second_active_member_grants_nothing_to_the_removed_one(
        self, mock_site_context
    ):
        """Pins the split-filter hazard: both cohort conditions -- membership
        by this user and that membership's Learner being active -- must be
        evaluated against the *same* joined membership row. A cohort holding
        the removed learner's membership alongside a second, unrelated,
        active learner's membership must not grant access to the removed one.
        """
        course = CourseFactory()
        removed_learner = LearnerFactory(is_active=False)
        cohort = _register_via_cohort(removed_learner, course)
        CohortMembershipFactory(
            learner=LearnerFactory(organisation=removed_learner.organisation),
            cohort=cohort,
        )

        _assert_both_agree(removed_learner.user, course, expected=False)


@pytest.mark.django_db
class TestNoRegistration:
    def test_a_user_with_no_registration_at_all_has_no_access(self, mock_site_context):
        course = CourseFactory()
        user = UserFactory()

        _assert_both_agree(user, course, expected=False)

    def test_a_registration_for_another_course_grants_nothing_for_this_one(
        self, mock_site_context
    ):
        course = CourseFactory()
        other_course = CourseFactory()
        learner = LearnerFactory()
        LearnerCourseRegistrationFactory(
            learner=learner, collection=other_course, is_active=True
        )

        _assert_both_agree(learner.user, course, expected=False)

    def test_anonymous_user_is_not_registered(self, mock_site_context):
        """Only is_registered_for_course takes a request user directly; the
        expression is always built for an authenticated learner's queryset."""
        course = CourseFactory()

        assert is_registered_for_course(AnonymousUser(), course) is False
