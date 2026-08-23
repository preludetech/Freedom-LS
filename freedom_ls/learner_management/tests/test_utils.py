"""Tests for learner_management.utils.is_registered_for_course and its
queryset-level mirror, learner_management.queries.is_registered_for_course_expression.

Both functions answer the same question -- direct registration or cohort
registration, gated on an active Learner -- so most scenarios below are
exercised through both to keep them from drifting apart.
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
from freedom_ls.learner_management.models import (
    Cohort,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.queries import is_registered_for_course_expression
from freedom_ls.learner_management.utils import is_registered_for_course
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation


def _make_learner(
    user: User, *, is_active: bool = True, organisation: Organisation | None = None
) -> Learner:
    learner = cast(
        Learner,
        LearnerFactory(user=user, organisation=organisation or OrganisationFactory()),
    )
    if not is_active:
        learner.is_active = False
        learner.save()
    return learner


def _register_directly(
    learner: Learner, course: Course, *, is_active: bool = True
) -> LearnerCourseRegistration:
    return cast(
        LearnerCourseRegistration,
        LearnerCourseRegistrationFactory(
            learner=learner, collection=course, is_active=is_active
        ),
    )


def _register_via_cohort(
    learner: Learner,
    course: Course,
    *,
    cohort: Cohort | None = None,
    is_active: bool = True,
) -> Cohort:
    """Put ``learner`` in ``cohort`` (a new one by default) and register that
    cohort for ``course``. Returns the cohort so a caller can add a second
    member to it."""
    cohort = cohort or cast(
        Cohort,
        CohortFactory(organisation=learner.organisation, name=f"Cohort {uuid.uuid4()}"),
    )
    CohortMembershipFactory(learner=learner, cohort=cohort)
    CohortCourseRegistrationFactory(
        cohort=cohort, collection=course, is_active=is_active
    )
    return cohort


def _expression_result(user: User, course: Course) -> bool:
    """Evaluate is_registered_for_course_expression for one course."""
    return bool(
        Course.objects.filter(pk=course.pk)
        .annotate(_registered=is_registered_for_course_expression(user))
        .get()
        ._registered
    )


def _assert_both_functions_agree(user: User, course: Course, *, expected: bool) -> None:
    assert is_registered_for_course(user, course) is expected
    assert _expression_result(user, course) is expected


@pytest.mark.django_db
class TestIsRegisteredForCourse:
    """Tests for learner_management.utils.is_registered_for_course."""

    def test_anonymous_user_is_not_registered(self, mock_site_context):
        course = CourseFactory()
        assert is_registered_for_course(AnonymousUser(), course) is False

    def test_directly_registered_active_learner_is_registered(self, mock_site_context):
        course = CourseFactory()
        user = UserFactory()
        learner = _make_learner(user)
        _register_directly(learner, course, is_active=True)

        assert is_registered_for_course(user, course) is True

    def test_inactive_direct_registration_is_not_registered(self, mock_site_context):
        course = CourseFactory()
        user = UserFactory()
        learner = _make_learner(user)
        _register_directly(learner, course, is_active=False)

        assert is_registered_for_course(user, course) is False

    def test_inactive_learner_is_not_registered_though_registration_is_active(
        self, mock_site_context
    ):
        """An active registration held by a removed Learner grants nothing:
        records are preserved, but access is suspended."""
        course = CourseFactory()
        user = UserFactory()
        learner = _make_learner(user, is_active=False)
        _register_directly(learner, course, is_active=True)

        assert is_registered_for_course(user, course) is False

    def test_cohort_registered_active_learner_is_registered(self, mock_site_context):
        course = CourseFactory()
        user = UserFactory()
        learner = _make_learner(user)
        _register_via_cohort(learner, course)

        assert is_registered_for_course(user, course) is True

    def test_inactive_learner_is_not_registered_through_cohort(self, mock_site_context):
        course = CourseFactory()
        user = UserFactory()
        learner = _make_learner(user, is_active=False)
        _register_via_cohort(learner, course)

        assert is_registered_for_course(user, course) is False

    def test_cohort_with_a_second_active_learner_still_grants_nothing_to_the_removed_one(
        self, mock_site_context
    ):
        """Pins the split-filter hazard: both cohort conditions -- membership
        by this user and that membership's Learner being active -- must be
        evaluated against the *same* joined membership row. A cohort holding
        the removed learner's membership alongside a second, unrelated,
        active learner's membership must not grant access to the removed one.
        """
        course = CourseFactory()
        removed_user = UserFactory()
        removed_learner = _make_learner(removed_user, is_active=False)
        cohort = _register_via_cohort(removed_learner, course)

        other_learner = _make_learner(
            UserFactory(), organisation=removed_learner.organisation
        )
        CohortMembershipFactory(learner=other_learner, cohort=cohort)

        assert is_registered_for_course(removed_user, course) is False

    def test_user_not_registered_at_all_returns_false(self, mock_site_context):
        course = CourseFactory()
        user = UserFactory()
        assert is_registered_for_course(user, course) is False

    def test_reactivating_learner_restores_access(self, mock_site_context):
        course = CourseFactory()
        user = UserFactory()
        learner = _make_learner(user, is_active=False)
        _register_directly(learner, course, is_active=True)
        assert is_registered_for_course(user, course) is False

        learner.is_active = True
        learner.save()

        assert is_registered_for_course(user, course) is True


@pytest.mark.django_db
class TestIsRegisteredForCourseExpression:
    """Tests for learner_management.queries.is_registered_for_course_expression."""

    def test_directly_registered_course_annotates_true(self, mock_site_context):
        course = CourseFactory()
        user = UserFactory()
        learner = _make_learner(user)
        _register_directly(learner, course, is_active=True)

        assert _expression_result(user, course) is True

    def test_cohort_registered_course_annotates_true(self, mock_site_context):
        course = CourseFactory()
        user = UserFactory()
        learner = _make_learner(user)
        _register_via_cohort(learner, course)

        assert _expression_result(user, course) is True

    def test_unregistered_course_annotates_false(self, mock_site_context):
        course_registered = CourseFactory()
        course_unrelated = CourseFactory()
        user = UserFactory()
        learner = _make_learner(user)
        _register_directly(learner, course_registered, is_active=True)

        assert _expression_result(user, course_unrelated) is False

    def test_inactive_learner_annotates_false_though_registration_is_active(
        self, mock_site_context
    ):
        course = CourseFactory()
        user = UserFactory()
        learner = _make_learner(user, is_active=False)
        _register_directly(learner, course, is_active=True)

        assert _expression_result(user, course) is False


@pytest.mark.django_db
class TestIsRegisteredForCourseAgreesWithItsExpression:
    """is_registered_for_course and is_registered_for_course_expression must
    always agree -- one gates the player, the other gates catalogue listings,
    and a learner must never see a course in one and be refused by the other.
    """

    def test_active_direct_registration(self, mock_site_context):
        course = CourseFactory()
        user = UserFactory()
        learner = _make_learner(user)
        _register_directly(learner, course, is_active=True)

        _assert_both_functions_agree(user, course, expected=True)

    def test_removed_learner_with_active_registration(self, mock_site_context):
        course = CourseFactory()
        user = UserFactory()
        learner = _make_learner(user, is_active=False)
        _register_directly(learner, course, is_active=True)

        _assert_both_functions_agree(user, course, expected=False)

    def test_removed_learner_with_active_cohort_registration(self, mock_site_context):
        course = CourseFactory()
        user = UserFactory()
        learner = _make_learner(user, is_active=False)
        _register_via_cohort(learner, course)

        _assert_both_functions_agree(user, course, expected=False)

    def test_cohort_with_a_second_active_learner_still_grants_nothing_to_the_removed_one(
        self, mock_site_context
    ):
        course = CourseFactory()
        removed_user = UserFactory()
        removed_learner = _make_learner(removed_user, is_active=False)
        cohort = _register_via_cohort(removed_learner, course)

        other_learner = _make_learner(
            UserFactory(), organisation=removed_learner.organisation
        )
        CohortMembershipFactory(learner=other_learner, cohort=cohort)

        _assert_both_functions_agree(removed_user, course, expected=False)

    def test_not_registered_at_all(self, mock_site_context):
        course = CourseFactory()
        user = UserFactory()

        _assert_both_functions_agree(user, course, expected=False)
