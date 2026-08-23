"""Tests for learner_management.queries helpers.

is_registered_for_course_expression is covered in test_utils.py alongside its
non-queryset sibling, is_registered_for_course. This module holds
latest_registration and the organisation-scoping helpers.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import cast

import pytest

from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

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
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.queries import (
    all_cohorts_visible_to,
    can_view_cohort,
    cohorts_visible_to,
    latest_registration,
    learners_visible_to,
    organisation_for_learner_course,
    organisations_accessible_to,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.utils import assign_object_role


def _make_cohort(*, organisation: Organisation | None = None) -> Cohort:
    return cast(
        Cohort,
        CohortFactory(
            organisation=organisation or OrganisationFactory(),
            name=f"Cohort {uuid.uuid4()}",
        ),
    )


def _make_registration(
    user: User,
    course: Course,
    *,
    organisation: Organisation | None = None,
    is_active: bool = True,
) -> LearnerCourseRegistration:
    learner = LearnerFactory(
        user=user, organisation=organisation or OrganisationFactory()
    )
    return cast(
        LearnerCourseRegistration,
        LearnerCourseRegistrationFactory(
            learner=learner, collection=course, is_active=is_active
        ),
    )


def _backdate(
    registration: LearnerCourseRegistration, when: datetime
) -> LearnerCourseRegistration:
    """Set registered_at directly, bypassing auto_now_add's save-time override."""
    LearnerCourseRegistration.objects.filter(pk=registration.pk).update(
        registered_at=when
    )
    registration.refresh_from_db()
    return registration


@pytest.mark.django_db
class TestLatestRegistration:
    """A learner can hold two registrations for one course, one per
    organisation. latest_registration picks a single deterministic row."""

    def test_no_registrations_returns_none(self, mock_site_context):
        user = UserFactory()
        course = CourseFactory()

        assert latest_registration(user, course) is None

    def test_single_active_registration_is_returned(self, mock_site_context):
        user = UserFactory()
        course = CourseFactory()
        registration = _make_registration(user, course, is_active=True)

        assert latest_registration(user, course) == registration

    def test_two_active_registrations_through_different_organisations_prefers_the_newer_one(
        self, mock_site_context
    ):
        user = UserFactory()
        course = CourseFactory()
        organisation_a = OrganisationFactory()
        organisation_b = OrganisationFactory()
        older = _make_registration(
            user, course, organisation=organisation_a, is_active=True
        )
        _backdate(older, timezone.now() - timedelta(days=7))
        newer = _make_registration(
            user, course, organisation=organisation_b, is_active=True
        )

        assert latest_registration(user, course) == newer

    def test_active_registration_wins_over_a_more_recent_inactive_one(
        self, mock_site_context
    ):
        user = UserFactory()
        course = CourseFactory()
        organisation_a = OrganisationFactory()
        organisation_b = OrganisationFactory()
        active = _make_registration(
            user, course, organisation=organisation_a, is_active=True
        )
        _backdate(active, timezone.now() - timedelta(days=7))
        _make_registration(user, course, organisation=organisation_b, is_active=False)

        assert latest_registration(user, course) == active

    def test_falls_back_to_most_recent_inactive_when_none_are_active(
        self, mock_site_context
    ):
        user = UserFactory()
        course = CourseFactory()
        organisation_a = OrganisationFactory()
        organisation_b = OrganisationFactory()
        older = _make_registration(
            user, course, organisation=organisation_a, is_active=False
        )
        _backdate(older, timezone.now() - timedelta(days=7))
        newer = _make_registration(
            user, course, organisation=organisation_b, is_active=False
        )

        assert latest_registration(user, course) == newer

    def test_ignores_registrations_for_a_different_course(self, mock_site_context):
        user = UserFactory()
        course = CourseFactory()
        other_course = CourseFactory()
        _make_registration(user, other_course, is_active=True)

        assert latest_registration(user, course) is None


@pytest.mark.django_db
class TestOrganisationsAccessibleTo:
    """An organisation is reachable via an organisation role or a per-cohort
    guardian grant on any cohort inside it."""

    def test_role_holder_sees_the_organisation(self, mock_site_context):
        organisation = OrganisationFactory()
        OrganisationFactory()  # decoy: held by nobody
        user = UserFactory()
        assign_object_role(user, organisation, "organisation_staff")

        assert list(organisations_accessible_to(user)) == [organisation]

    def test_guardian_grant_on_a_cohort_grants_the_organisation(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        OrganisationFactory()  # decoy: no cohort of this one is granted
        cohort = _make_cohort(organisation=organisation)
        user = UserFactory()
        assign_object_role(user, cohort, "instructor")

        assert list(organisations_accessible_to(user)) == [organisation]

    def test_organisations_are_returned_in_name_order(self, mock_site_context):
        """The switcher renders them in the order this helper returns."""
        zebra = OrganisationFactory(name="Zebra Academy")
        acacia = OrganisationFactory(name="Acacia College")
        user = UserFactory()
        assign_object_role(user, zebra, "organisation_staff")
        assign_object_role(user, acacia, "organisation_staff")

        assert list(organisations_accessible_to(user)) == [acacia, zebra]

    def test_user_with_both_role_and_grant_sees_the_organisation_once(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        cohort = _make_cohort(organisation=organisation)
        user = UserFactory()
        assign_object_role(user, organisation, "organisation_staff")
        assign_object_role(user, cohort, "instructor")

        accessible = organisations_accessible_to(user)

        assert list(accessible).count(organisation) == 1

    def test_anonymous_user_sees_no_organisations(self, mock_site_context):
        OrganisationFactory()

        assert list(organisations_accessible_to(AnonymousUser())) == []

    def test_user_with_neither_role_nor_grant_sees_no_organisations(
        self, mock_site_context
    ):
        OrganisationFactory()
        user = UserFactory()

        assert list(organisations_accessible_to(user)) == []


@pytest.mark.django_db
class TestCohortsVisibleTo:
    """All cohorts in the organisation for a role holder; only the granted
    ones for a guardian-grant-only educator."""

    def test_role_holder_sees_every_cohort_in_the_organisation(self, mock_site_context):
        organisation = OrganisationFactory()
        cohort_a = _make_cohort(organisation=organisation)
        cohort_b = _make_cohort(organisation=organisation)
        user = UserFactory()
        assign_object_role(user, organisation, "organisation_staff")

        visible = cohorts_visible_to(user, organisation)

        assert set(visible) == {cohort_a, cohort_b}

    def test_guardian_grant_only_sees_the_granted_cohort(self, mock_site_context):
        organisation = OrganisationFactory()
        granted_cohort = _make_cohort(organisation=organisation)
        _make_cohort(organisation=organisation)
        user = UserFactory()
        assign_object_role(user, granted_cohort, "instructor")

        visible = cohorts_visible_to(user, organisation)

        assert list(visible) == [granted_cohort]

    def test_anonymous_user_sees_no_cohorts(self, mock_site_context):
        organisation = OrganisationFactory()
        _make_cohort(organisation=organisation)

        assert list(cohorts_visible_to(AnonymousUser(), organisation)) == []

    def test_user_with_neither_role_nor_grant_sees_no_cohorts(self, mock_site_context):
        organisation = OrganisationFactory()
        _make_cohort(organisation=organisation)
        user = UserFactory()

        assert list(cohorts_visible_to(user, organisation)) == []


@pytest.mark.django_db
class TestAllCohortsVisibleTo:
    """The organisation-unscoped sibling of cohorts_visible_to, for surfaces
    with no organisation in scope."""

    def test_role_holder_sees_every_cohort_in_their_organisation(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        cohort_a = _make_cohort(organisation=organisation)
        cohort_b = _make_cohort(organisation=organisation)
        user = UserFactory()
        assign_object_role(user, organisation, "organisation_staff")

        assert set(all_cohorts_visible_to(user)) == {cohort_a, cohort_b}

    def test_cohorts_in_another_organisation_are_excluded(self, mock_site_context):
        organisation = OrganisationFactory()
        mine = _make_cohort(organisation=organisation)
        _make_cohort(organisation=OrganisationFactory())
        user = UserFactory()
        assign_object_role(user, organisation, "organisation_staff")

        assert list(all_cohorts_visible_to(user)) == [mine]

    def test_guardian_grant_only_sees_the_granted_cohort(self, mock_site_context):
        organisation = OrganisationFactory()
        granted = _make_cohort(organisation=organisation)
        _make_cohort(organisation=organisation)
        user = UserFactory()
        assign_object_role(user, granted, "instructor")

        assert list(all_cohorts_visible_to(user)) == [granted]

    def test_roles_in_two_organisations_are_unioned(self, mock_site_context):
        first = OrganisationFactory()
        second = OrganisationFactory()
        cohort_a = _make_cohort(organisation=first)
        cohort_b = _make_cohort(organisation=second)
        user = UserFactory()
        assign_object_role(user, first, "organisation_staff")
        assign_object_role(user, second, "organisation_staff")

        assert set(all_cohorts_visible_to(user)) == {cohort_a, cohort_b}

    def test_both_paths_return_each_cohort_once(self, mock_site_context):
        organisation = OrganisationFactory()
        cohort = _make_cohort(organisation=organisation)
        user = UserFactory()
        assign_object_role(user, organisation, "organisation_staff")
        assign_object_role(user, cohort, "instructor")

        assert list(all_cohorts_visible_to(user)).count(cohort) == 1

    def test_anonymous_user_sees_no_cohorts(self, mock_site_context):
        _make_cohort()

        assert list(all_cohorts_visible_to(AnonymousUser())) == []

    def test_user_with_neither_role_nor_grant_sees_no_cohorts(self, mock_site_context):
        _make_cohort()
        user = UserFactory()

        assert list(all_cohorts_visible_to(user)) == []


@pytest.mark.django_db
class TestCanViewCohort:
    """The per-object check behind the report admin's permission hooks."""

    def test_role_holder_may_view_a_cohort_in_their_organisation(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        cohort = _make_cohort(organisation=organisation)
        user = UserFactory()
        assign_object_role(user, organisation, "organisation_staff")

        assert can_view_cohort(user, cohort) is True

    def test_role_holder_may_not_view_a_cohort_in_another_organisation(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        foreign_cohort = _make_cohort(organisation=OrganisationFactory())
        user = UserFactory()
        assign_object_role(user, organisation, "organisation_staff")

        assert can_view_cohort(user, foreign_cohort) is False

    def test_guardian_grant_holder_may_view_the_granted_cohort(self, mock_site_context):
        cohort = _make_cohort()
        user = UserFactory()
        assign_object_role(user, cohort, "instructor")

        assert can_view_cohort(user, cohort) is True

    def test_guardian_grant_holder_may_not_view_a_sibling_cohort(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        granted = _make_cohort(organisation=organisation)
        sibling = _make_cohort(organisation=organisation)
        user = UserFactory()
        assign_object_role(user, granted, "instructor")

        assert can_view_cohort(user, sibling) is False

    def test_anonymous_user_may_view_nothing(self, mock_site_context):
        cohort = _make_cohort()

        assert can_view_cohort(AnonymousUser(), cohort) is False

    def test_user_with_neither_role_nor_grant_may_view_nothing(self, mock_site_context):
        cohort = _make_cohort()
        user = UserFactory()

        assert can_view_cohort(user, cohort) is False


@pytest.mark.django_db
class TestLearnersVisibleTo:
    """Members of visible cohorts, plus — for an organisation-role holder
    only — every learner associated with the organisation."""

    def test_learner_with_no_enrolment_is_visible_to_an_organisation_role_holder(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        learner = LearnerFactory(user=UserFactory(), organisation=organisation)
        role_holder = UserFactory()
        assign_object_role(role_holder, organisation, "organisation_staff")

        assert set(learners_visible_to(role_holder, organisation)) == {learner}

    def test_inactive_learner_is_not_visible_to_an_organisation_role_holder(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        LearnerFactory(user=UserFactory(), organisation=organisation, is_active=False)
        role_holder = UserFactory()
        assign_object_role(role_holder, organisation, "organisation_staff")

        assert list(learners_visible_to(role_holder, organisation)) == []

    def test_removed_learner_still_in_a_visible_cohort_is_not_visible(
        self, mock_site_context
    ):
        """Pins is_active sitting outside both Q branches: a removed learner
        who still holds a membership in a visible cohort must not reappear
        through the cohort branch."""
        organisation = OrganisationFactory()
        cohort = _make_cohort(organisation=organisation)
        removed_learner = LearnerFactory(
            user=UserFactory(), organisation=organisation, is_active=False
        )
        CohortMembershipFactory(learner=removed_learner, cohort=cohort)
        role_holder = UserFactory()
        assign_object_role(role_holder, organisation, "organisation_staff")

        assert list(learners_visible_to(role_holder, organisation)) == []

    def test_learner_in_another_organisation_is_not_visible(self, mock_site_context):
        organisation = OrganisationFactory()
        LearnerFactory(user=UserFactory(), organisation=OrganisationFactory())
        role_holder = UserFactory()
        assign_object_role(role_holder, organisation, "organisation_staff")

        assert list(learners_visible_to(role_holder, organisation)) == []

    def test_cohort_only_educator_sees_exactly_their_cohorts_members(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        granted_cohort = _make_cohort(organisation=organisation)
        other_cohort = _make_cohort(organisation=organisation)
        granted_member = LearnerFactory(user=UserFactory(), organisation=organisation)
        CohortMembershipFactory(learner=granted_member, cohort=granted_cohort)
        CohortMembershipFactory(
            learner=LearnerFactory(user=UserFactory(), organisation=organisation),
            cohort=other_cohort,
        )
        # Associated with the organisation directly, no cohort at all -- only
        # an organisation-role holder would see this one.
        LearnerFactory(user=UserFactory(), organisation=organisation)
        educator = UserFactory()
        assign_object_role(educator, granted_cohort, "instructor")

        assert set(learners_visible_to(educator, organisation)) == {granted_member}

    def test_anonymous_user_sees_no_learners(self, mock_site_context):
        organisation = OrganisationFactory()
        LearnerFactory(user=UserFactory(), organisation=organisation)

        assert list(learners_visible_to(AnonymousUser(), organisation)) == []

    def test_user_with_neither_role_nor_grant_sees_no_learners(self, mock_site_context):
        organisation = OrganisationFactory()
        LearnerFactory(user=UserFactory(), organisation=organisation)
        user = UserFactory()

        assert list(learners_visible_to(user, organisation)) == []


@pytest.mark.django_db
class TestOrganisationForLearnerCourse:
    """Cohort registration wins over an individual one; with neither, there is
    no organisation to report. The duplicate-registration tiebreak is
    delegated to latest_registration and tested there."""

    def test_no_registration_returns_none(self, mock_site_context):
        course = CourseFactory()
        user = UserFactory()

        assert organisation_for_learner_course(user, course) is None

    def test_cohort_registration_wins_over_an_individual_one(self, mock_site_context):
        course = CourseFactory()
        user = UserFactory()
        cohort_organisation = OrganisationFactory()
        individual_organisation = OrganisationFactory()
        cohort = _make_cohort(organisation=cohort_organisation)
        cohort_learner = LearnerFactory(user=user, organisation=cohort_organisation)
        CohortMembershipFactory(learner=cohort_learner, cohort=cohort)
        CohortCourseRegistrationFactory(cohort=cohort, collection=course)
        _make_registration(user, course, organisation=individual_organisation)

        assert organisation_for_learner_course(user, course) == cohort_organisation

    def test_individual_registration_only_uses_its_organisation(
        self, mock_site_context
    ):
        course = CourseFactory()
        user = UserFactory()
        organisation = OrganisationFactory()
        _make_registration(user, course, organisation=organisation)

        assert organisation_for_learner_course(user, course) == organisation

    def test_removed_learner_in_a_cohort_yields_no_organisation_though_another_member_is_active(
        self, mock_site_context
    ):
        """Pins the same split-filter hazard as is_registered_for_course: the
        membership-by-this-user condition and the is_active condition must be
        evaluated against the same joined membership row, or a cohort holding
        a removed learner alongside an unrelated active one would still name
        an organisation the removed learner was cut off from."""
        course = CourseFactory()
        organisation = OrganisationFactory()
        removed_user = UserFactory()
        removed_learner = LearnerFactory(
            user=removed_user, organisation=organisation, is_active=False
        )
        cohort = _make_cohort(organisation=organisation)
        CohortMembershipFactory(learner=removed_learner, cohort=cohort)
        CohortCourseRegistrationFactory(cohort=cohort, collection=course)
        other_learner = LearnerFactory(user=UserFactory(), organisation=organisation)
        CohortMembershipFactory(learner=other_learner, cohort=cohort)

        assert organisation_for_learner_course(removed_user, course) is None


@pytest.mark.django_db
class TestOrganisationForLearnerCourseQueryCount:
    """The resolver's cost must not grow with how many registrations a
    learner happens to hold, so the same ceiling has to hold for one
    duplicate and for five."""

    @pytest.mark.parametrize("duplicates", [1, 5])
    def test_cohort_path_never_looks_at_individual_registrations(
        self, mock_site_context, django_assert_max_num_queries, duplicates
    ):
        course = CourseFactory()
        user = UserFactory()
        organisation = OrganisationFactory()
        cohort = _make_cohort(organisation=organisation)
        cohort_learner = LearnerFactory(user=user, organisation=organisation)
        CohortMembershipFactory(learner=cohort_learner, cohort=cohort)
        CohortCourseRegistrationFactory(cohort=cohort, collection=course)
        for _ in range(duplicates):
            _make_registration(user, course)

        with django_assert_max_num_queries(1):
            organisation_for_learner_course(user, course)

    @pytest.mark.parametrize("duplicates", [1, 5])
    def test_individual_path_does_not_grow_with_duplicates(
        self, mock_site_context, django_assert_max_num_queries, duplicates
    ):
        course = CourseFactory()
        user = UserFactory()
        for _ in range(duplicates):
            _make_registration(user, course)

        with django_assert_max_num_queries(2):
            organisation_for_learner_course(user, course)
