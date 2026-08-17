"""Tests for student_management.queries helpers.

is_registered_for_course_expression is covered in test_utils.py alongside its
non-queryset sibling, is_registered_for_course. This module holds
latest_registration and the organisation-scoping helpers.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role
from freedom_ls.student_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
    UserCourseRegistrationFactory,
)
from freedom_ls.student_management.models import UserCourseRegistration
from freedom_ls.student_management.queries import (
    cohorts_visible_to,
    latest_registration,
    organisations_accessible_to,
    users_visible_to,
)


def _backdate(registration: UserCourseRegistration, when) -> UserCourseRegistration:
    """Set registered_at directly, bypassing auto_now_add's save-time override."""
    UserCourseRegistration.objects.filter(pk=registration.pk).update(registered_at=when)
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
        registration = UserCourseRegistrationFactory(
            user=user, collection=course, is_active=True
        )

        assert latest_registration(user, course) == registration

    def test_two_active_registrations_through_different_organisations_prefers_the_newer_one(
        self, mock_site_context
    ):
        user = UserFactory()
        course = CourseFactory()
        organisation_a = OrganisationFactory()
        organisation_b = OrganisationFactory()
        older = UserCourseRegistrationFactory(
            user=user, collection=course, organisation=organisation_a, is_active=True
        )
        _backdate(older, timezone.now() - timedelta(days=7))
        newer = UserCourseRegistrationFactory(
            user=user, collection=course, organisation=organisation_b, is_active=True
        )

        assert latest_registration(user, course) == newer

    def test_active_registration_wins_over_a_more_recent_inactive_one(
        self, mock_site_context
    ):
        user = UserFactory()
        course = CourseFactory()
        organisation_a = OrganisationFactory()
        organisation_b = OrganisationFactory()
        active = UserCourseRegistrationFactory(
            user=user, collection=course, organisation=organisation_a, is_active=True
        )
        _backdate(active, timezone.now() - timedelta(days=7))
        UserCourseRegistrationFactory(
            user=user, collection=course, organisation=organisation_b, is_active=False
        )

        assert latest_registration(user, course) == active

    def test_falls_back_to_most_recent_inactive_when_none_are_active(
        self, mock_site_context
    ):
        user = UserFactory()
        course = CourseFactory()
        organisation_a = OrganisationFactory()
        organisation_b = OrganisationFactory()
        older = UserCourseRegistrationFactory(
            user=user, collection=course, organisation=organisation_a, is_active=False
        )
        _backdate(older, timezone.now() - timedelta(days=7))
        newer = UserCourseRegistrationFactory(
            user=user, collection=course, organisation=organisation_b, is_active=False
        )

        assert latest_registration(user, course) == newer

    def test_ignores_registrations_for_a_different_course(self, mock_site_context):
        user = UserFactory()
        course = CourseFactory()
        other_course = CourseFactory()
        UserCourseRegistrationFactory(
            user=user, collection=other_course, is_active=True
        )

        assert latest_registration(user, course) is None


@pytest.mark.django_db
class TestOrganisationsAccessibleTo:
    """An organisation is reachable via an organisation role or a per-cohort
    guardian grant on any cohort inside it."""

    def test_role_holder_sees_the_organisation(self, mock_site_context):
        organisation = OrganisationFactory()
        user = UserFactory()
        assign_object_role(user, organisation, "organisation_staff")

        assert organisation in organisations_accessible_to(user)

    def test_guardian_grant_on_a_cohort_grants_the_organisation(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)
        user = UserFactory()
        assign_object_role(user, cohort, "instructor")

        assert organisation in organisations_accessible_to(user)

    def test_user_with_both_role_and_grant_sees_the_organisation_once(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)
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
        cohort_a = CohortFactory(organisation=organisation)
        cohort_b = CohortFactory(organisation=organisation)
        user = UserFactory()
        assign_object_role(user, organisation, "organisation_staff")

        visible = cohorts_visible_to(user, organisation)

        assert set(visible) == {cohort_a, cohort_b}

    def test_guardian_grant_only_sees_the_granted_cohort(self, mock_site_context):
        organisation = OrganisationFactory()
        granted_cohort = CohortFactory(organisation=organisation)
        CohortFactory(organisation=organisation)
        user = UserFactory()
        assign_object_role(user, granted_cohort, "instructor")

        visible = cohorts_visible_to(user, organisation)

        assert list(visible) == [granted_cohort]

    def test_anonymous_user_sees_no_cohorts(self, mock_site_context):
        organisation = OrganisationFactory()
        CohortFactory(organisation=organisation)

        assert list(cohorts_visible_to(AnonymousUser(), organisation)) == []

    def test_user_with_neither_role_nor_grant_sees_no_cohorts(self, mock_site_context):
        organisation = OrganisationFactory()
        CohortFactory(organisation=organisation)
        user = UserFactory()

        assert list(cohorts_visible_to(user, organisation)) == []


@pytest.mark.django_db
class TestUsersVisibleTo:
    """Members of visible cohorts, plus — for an organisation-role holder
    only — individually-registered learners with no cohort at all."""

    def test_role_holder_sees_cohort_members(self, mock_site_context):
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)
        member = UserFactory()
        CohortMembershipFactory(cohort=cohort, user=member)
        role_holder = UserFactory()
        assign_object_role(role_holder, organisation, "organisation_staff")

        assert member in users_visible_to(role_holder, organisation)

    def test_guardian_grant_only_sees_members_of_the_granted_cohort_only(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        granted_cohort = CohortFactory(organisation=organisation)
        other_cohort = CohortFactory(organisation=organisation)
        granted_member = UserFactory()
        other_member = UserFactory()
        CohortMembershipFactory(cohort=granted_cohort, user=granted_member)
        CohortMembershipFactory(cohort=other_cohort, user=other_member)
        educator = UserFactory()
        assign_object_role(educator, granted_cohort, "instructor")

        visible = users_visible_to(educator, organisation)

        assert granted_member in visible
        assert other_member not in visible

    def test_individually_registered_learner_visible_to_the_role_holder(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        learner = UserFactory()
        UserCourseRegistrationFactory(user=learner, organisation=organisation)
        role_holder = UserFactory()
        assign_object_role(role_holder, organisation, "organisation_staff")

        assert learner in users_visible_to(role_holder, organisation)

    def test_individually_registered_learner_not_visible_to_guardian_grant_only_educator(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        learner = UserFactory()
        UserCourseRegistrationFactory(user=learner, organisation=organisation)
        cohort = CohortFactory(organisation=organisation)
        educator = UserFactory()
        assign_object_role(educator, cohort, "instructor")

        assert learner not in users_visible_to(educator, organisation)

    def test_anonymous_user_sees_no_users(self, mock_site_context):
        organisation = OrganisationFactory()
        learner = UserFactory()
        UserCourseRegistrationFactory(user=learner, organisation=organisation)

        assert list(users_visible_to(AnonymousUser(), organisation)) == []

    def test_user_with_neither_role_nor_grant_sees_no_users(self, mock_site_context):
        organisation = OrganisationFactory()
        learner = UserFactory()
        UserCourseRegistrationFactory(user=learner, organisation=organisation)
        user = UserFactory()

        assert list(users_visible_to(user, organisation)) == []
