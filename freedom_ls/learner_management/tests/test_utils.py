"""Tests for learner_management.utils.is_registered_for_course and its
queryset-level mirror, learner_management.queries.is_registered_for_course_expression.

Both functions answer the same question -- direct registration or cohort
registration, gated on an active Learner. One gates the player, the other
gates catalogue listings, and a learner must never see a course in one and be
refused by the other, so every scenario they share is asserted through both
at once via ``_assert_both_agree``. Only the cases one function has and the
other does not get their own test."""

from __future__ import annotations

import uuid
from typing import cast

import pytest

from django.contrib.auth.models import AnonymousUser

from freedom_ls.accounts.factories import SiteFactory, UserFactory
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
from freedom_ls.learner_management.models import Cohort, Learner, OrganisationMember
from freedom_ls.learner_management.queries import is_registered_for_course_expression
from freedom_ls.learner_management.utils import (
    ensure_learner,
    ensure_organisation_member,
    is_registered_for_course,
)
from freedom_ls.organisations.factories import OrganisationFactory


def _register_via_cohort(learner: Learner, course: Course) -> Cohort:
    """Put ``learner`` in a new cohort and register that cohort for ``course``.
    Returns the cohort so a caller can add a second member to it."""
    cohort = cast(
        Cohort,
        CohortFactory(organisation=learner.organisation, name=f"Cohort {uuid.uuid4()}"),
    )
    CohortMembershipFactory(learner=learner, cohort=cohort)
    CohortCourseRegistrationFactory(cohort=cohort, course=course, is_active=True)
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
        LearnerCourseRegistrationFactory(learner=learner, course=course, is_active=True)

        _assert_both_agree(learner.user, course, expected=True)

    def test_inactive_registration_grants_nothing(self, mock_site_context):
        course = CourseFactory()
        learner = LearnerFactory()
        LearnerCourseRegistrationFactory(
            learner=learner, course=course, is_active=False
        )

        _assert_both_agree(learner.user, course, expected=False)

    def test_removed_learner_grants_nothing_though_registration_is_active(
        self, mock_site_context
    ):
        """An active registration held by a removed Learner grants nothing:
        records are preserved, but access is suspended."""
        course = CourseFactory()
        learner = LearnerFactory(is_active=False)
        LearnerCourseRegistrationFactory(learner=learner, course=course, is_active=True)

        _assert_both_agree(learner.user, course, expected=False)

    def test_reactivating_a_removed_learner_restores_access(self, mock_site_context):
        course = CourseFactory()
        learner = LearnerFactory(is_active=False)
        LearnerCourseRegistrationFactory(learner=learner, course=course, is_active=True)

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
class TestInactiveCohort:
    def test_a_member_of_an_inactive_cohort_has_no_access_through_it(
        self, mock_site_context
    ):
        course = CourseFactory()
        learner = LearnerFactory()
        cohort = _register_via_cohort(learner, course)
        cohort.is_active = False
        cohort.save()

        _assert_both_agree(learner.user, course, expected=False)

    def test_an_individual_registration_still_grants_access(self, mock_site_context):
        course = CourseFactory()
        learner = LearnerFactory()
        cohort = _register_via_cohort(learner, course)
        cohort.is_active = False
        cohort.save()
        LearnerCourseRegistrationFactory(learner=learner, course=course, is_active=True)

        _assert_both_agree(learner.user, course, expected=True)

    def test_an_active_registration_in_a_second_cohort_still_grants_access(
        self, mock_site_context
    ):
        course = CourseFactory()
        learner = LearnerFactory()
        inactive_cohort = _register_via_cohort(learner, course)
        inactive_cohort.is_active = False
        inactive_cohort.save()
        _register_via_cohort(learner, course)

        _assert_both_agree(learner.user, course, expected=True)

    def test_reactivating_the_cohort_restores_access(self, mock_site_context):
        course = CourseFactory()
        learner = LearnerFactory()
        cohort = _register_via_cohort(learner, course)
        cohort.is_active = False
        cohort.save()

        cohort.is_active = True
        cohort.save()

        _assert_both_agree(learner.user, course, expected=True)


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
            learner=learner, course=other_course, is_active=True
        )

        _assert_both_agree(learner.user, course, expected=False)

    def test_anonymous_user_is_not_registered(self, mock_site_context):
        """Only is_registered_for_course takes a request user directly; the
        expression is always built for an authenticated learner's queryset."""
        course = CourseFactory()

        assert is_registered_for_course(AnonymousUser(), course) is False


# Tests for ensure_learner, the idempotent get-or-reactivate helper.


@pytest.mark.django_db
class TestEnsureLearner:
    """Arranged with Learner.objects.create, not LearnerFactory: the factory
    delegates to ensure_learner, so building the starting state with it would
    test the function against itself."""

    def test_calling_twice_creates_one_row(self, mock_site_context):
        user = UserFactory()
        organisation = OrganisationFactory()

        ensure_learner(user, organisation)
        ensure_learner(user, organisation)

        assert Learner.objects.filter(user=user, organisation=organisation).count() == 1

    def test_calling_twice_returns_the_same_row(self, mock_site_context):
        user = UserFactory()
        organisation = OrganisationFactory()

        first = ensure_learner(user, organisation)
        second = ensure_learner(user, organisation)

        assert first.pk == second.pk

    def test_reactivates_a_removed_learner(self, mock_site_context):
        user = UserFactory()
        organisation = OrganisationFactory()
        learner = Learner.objects.create(
            user=user, organisation=organisation, is_active=False
        )

        ensure_learner(user, organisation)

        learner.refresh_from_db()
        assert learner.is_active is True

    def test_finds_the_existing_row_when_a_different_site_is_ambient(
        self, mock_site_context
    ):
        """The organisation being handled is not always the site the current
        request is for. Using the site-aware manager for the lookup half of
        update_or_create would AND the ambient site onto the query, miss the
        row created below, and attempt a second INSERT — raising
        IntegrityError on unique_learner_per_organisation. A test that only
        calls ensure_learner once passes against that broken version too."""
        user = UserFactory()
        organisation = OrganisationFactory(site=SiteFactory())

        ensure_learner(user, organisation)
        ensure_learner(user, organisation)

        assert (
            Learner._base_manager.filter(user=user, organisation=organisation).count()
            == 1
        )


# Tests for ensure_organisation_member, the get-or-create gate helper.
#
# Unlike ensure_learner, this never reactivates an existing row: a deactivated
# member must stay deactivated until someone explicitly reactivates them.


@pytest.mark.django_db
class TestEnsureOrganisationMember:
    """Arranged with OrganisationMember.objects.create, not
    OrganisationMemberFactory: the factory is a thin wrapper over the model,
    but building starting state through the function under test would still
    test it against itself, so a raw create keeps the arrangement independent."""

    def test_creates_a_row(self, mock_site_context):
        user = UserFactory()
        organisation = OrganisationFactory()

        member = ensure_organisation_member(user, organisation)

        assert member.pk is not None
        assert member.user == user
        assert member.organisation == organisation
        assert member.is_active is True

    def test_returns_an_existing_active_row_unchanged(self, mock_site_context):
        user = UserFactory()
        organisation = OrganisationFactory()
        existing = OrganisationMember.objects.create(
            user=user, organisation=organisation, is_active=True
        )

        returned = ensure_organisation_member(user, organisation)

        assert returned.pk == existing.pk
        assert (
            OrganisationMember.objects.filter(
                user=user, organisation=organisation
            ).count()
            == 1
        )

    def test_returns_an_inactive_row_still_inactive(self, mock_site_context):
        user = UserFactory()
        organisation = OrganisationFactory()
        existing = OrganisationMember.objects.create(
            user=user, organisation=organisation, is_active=False
        )

        returned = ensure_organisation_member(user, organisation)

        assert returned.pk == existing.pk
        assert returned.is_active is False

    def test_finds_the_existing_row_when_a_different_site_is_ambient(
        self, mock_site_context
    ):
        """Mirrors ensure_learner's own version of this test: the lookup must
        use _base_manager, or an ambient site foreign to the organisation
        being handled makes get_or_create miss the row below and attempt a
        second INSERT, raising IntegrityError on
        unique_member_per_organisation."""
        user = UserFactory()
        organisation = OrganisationFactory(site=SiteFactory())

        ensure_organisation_member(user, organisation)
        ensure_organisation_member(user, organisation)

        assert (
            OrganisationMember._base_manager.filter(
                user=user, organisation=organisation
            ).count()
            == 1
        )
