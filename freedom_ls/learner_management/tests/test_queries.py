"""Tests for learner_management.queries helpers.

is_registered_for_course_expression is covered in test_utils.py alongside its
non-queryset sibling, is_registered_for_course. This module holds
latest_registration, learner_for_course and the organisation-scoping helpers.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import cast

import pytest
from guardian.shortcuts import assign_perm
from pytest_mock import MockerFixture

from django.contrib.auth.models import AnonymousUser
from django.contrib.sites.models import Site
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course, CourseVisibility
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    Learner,
    LearnerCourseRegistration,
    OrganisationMember,
)
from freedom_ls.learner_management.queries import (
    DELETE_COHORTMEMBERSHIP,
    CohortCounts,
    LearnerStatus,
    ResolvedRegistration,
    active_organisation_admins,
    all_cohorts_visible_to,
    can_view_cohort,
    cohort_counts,
    cohort_course_count,
    cohort_educators,
    cohort_is_empty,
    cohort_learner_count,
    cohorts_visible_to,
    colleagues_of,
    courses_gaining_access,
    courses_losing_access,
    educators_of,
    holds_registration_for_any_expression,
    in_audience_expression,
    is_in_audience,
    is_registered_for_course_expression,
    latest_registration,
    learner_for_course,
    learner_status,
    learner_status_q,
    learners_visible_to,
    members_keeping_access,
    members_of,
    organisation_for_learner_course,
    organisations_accessible_to,
    other_grants_for,
    peers_of,
    peers_through,
    registerable_courses_for,
    registerable_courses_for_learner,
    registered_course_pairs,
    site_level_admins,
)
from freedom_ls.learner_management.tests.helpers import AUDIENCE_CASES
from freedom_ls.learner_management.tests.scenario_world import (
    World,
    educator_names,
    educator_pairs,
    visible_pairs,
)
from freedom_ls.learner_management.utils import is_registered_for_course
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.role_based_permissions.loader import get_role_config
from freedom_ls.role_based_permissions.models import SiteRoleAssignment
from freedom_ls.role_based_permissions.roles import BASE_ROLES
from freedom_ls.role_based_permissions.types import SCOPE_OBJECT, Role, SiteRolesConfig
from freedom_ls.role_based_permissions.utils import (
    assign_object_role,
    assign_site_role,
    remove_object_role,
)
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import drop_ambient_request, site_context


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
            learner=learner, course=course, is_active=is_active
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


def _backdate_cohort_registration(
    registration: CohortCourseRegistration, when: datetime
) -> CohortCourseRegistration:
    """Set registered_at directly, bypassing auto_now_add's save-time override."""
    CohortCourseRegistration.objects.filter(pk=registration.pk).update(
        registered_at=when
    )
    registration.refresh_from_db()
    return registration


@pytest.mark.django_db
class TestInAudience:
    @pytest.mark.parametrize("case", AUDIENCE_CASES)
    def test_single_course_form_matches_the_case_table(
        self, mock_site_context: Site, case: str
    ) -> None:
        build, expected = AUDIENCE_CASES[case]
        user, course = build()

        assert is_in_audience(user, course) is expected

    @pytest.mark.parametrize("case", AUDIENCE_CASES)
    def test_queryset_form_matches_the_case_table(
        self, mock_site_context: Site, case: str
    ) -> None:
        build, expected = AUDIENCE_CASES[case]
        user, course = build()

        listed = (
            Course.objects.filter(pk=course.pk)
            .filter(in_audience_expression(user))
            .exists()
        )

        assert listed is expected


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

    def test_a_live_learners_registration_beats_a_removed_learners_newer_one(
        self, mock_site_context
    ):
        """The row that actually grants access sorts ahead of the one that does not.

        Both registrations are active, so recency alone would hand over the
        more recent one -- and with it the Learner keying the course progress
        record -- even though its Learner has been removed and every access
        check is satisfied by the other one.
        """
        user = UserFactory()
        course = CourseFactory()
        live = _make_registration(
            user, course, organisation=OrganisationFactory(), is_active=True
        )
        _backdate(live, timezone.now() - timedelta(days=7))
        removed = _make_registration(
            user, course, organisation=OrganisationFactory(), is_active=True
        )
        removed.learner.is_active = False
        removed.learner.save(update_fields=["is_active"])

        assert latest_registration(user, course) == live

    def test_a_removed_learners_registration_is_still_returned_on_its_own(
        self, mock_site_context
    ):
        """is_active is a tiebreak, not a filter: a removed learner still
        resolves to their own registration, which is what keeps their own
        registration resolvable."""
        user = UserFactory()
        course = CourseFactory()
        registration = _make_registration(user, course, is_active=True)
        registration.learner.is_active = False
        registration.learner.save(update_fields=["is_active"])

        assert latest_registration(user, course) == registration

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
    role assignment on any cohort inside it."""

    def test_role_holder_sees_the_organisation(self, mock_site_context):
        organisation = OrganisationFactory()
        OrganisationFactory()  # decoy: held by nobody
        user = UserFactory()
        assign_object_role(user, organisation, "organisation_admin")

        assert list(organisations_accessible_to(user)) == [organisation]

    def test_guardian_grant_on_a_cohort_grants_the_organisation(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        OrganisationFactory()  # decoy: no cohort of this one is granted
        cohort = _make_cohort(organisation=organisation)
        user = UserFactory()
        assign_object_role(user, cohort, "cohort_admin")

        assert list(organisations_accessible_to(user)) == [organisation]

    def test_organisations_are_returned_in_name_order(self, mock_site_context):
        """The switcher renders them in the order this helper returns."""
        zebra = OrganisationFactory(name="Zebra Academy")
        acacia = OrganisationFactory(name="Acacia College")
        user = UserFactory()
        assign_object_role(user, zebra, "organisation_admin")
        assign_object_role(user, acacia, "organisation_admin")

        assert list(organisations_accessible_to(user)) == [acacia, zebra]

    def test_user_with_both_role_and_grant_sees_the_organisation_once(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        cohort = _make_cohort(organisation=organisation)
        user = UserFactory()
        assign_object_role(user, organisation, "organisation_admin")
        assign_object_role(user, cohort, "cohort_admin")

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

    def test_site_admin_sees_every_organisation_on_its_site(self, mock_site_context):
        organisation_a = OrganisationFactory()
        organisation_b = OrganisationFactory()
        user = UserFactory()
        assign_site_role(user, "site_admin", site=mock_site_context)

        # get_default_organisation, not another OrganisationFactory(): every
        # Site already carries one of its own, made by a post_save receiver,
        # so the site admin must see it too.
        default_organisation = get_default_organisation(mock_site_context)
        assert set(organisations_accessible_to(user)) == {
            organisation_a,
            organisation_b,
            default_organisation,
        }


@pytest.mark.django_db
class TestCohortsVisibleTo:
    """All cohorts in the organisation for a role holder; only the granted
    ones for an educator holding only a per-cohort role assignment."""

    def test_role_holder_sees_every_cohort_in_the_organisation(self, mock_site_context):
        organisation = OrganisationFactory()
        cohort_a = _make_cohort(organisation=organisation)
        cohort_b = _make_cohort(organisation=organisation)
        user = UserFactory()
        assign_object_role(user, organisation, "organisation_admin")

        visible = cohorts_visible_to(user, organisation)

        assert set(visible) == {cohort_a, cohort_b}

    def test_guardian_grant_only_sees_the_granted_cohort(self, mock_site_context):
        organisation = OrganisationFactory()
        granted_cohort = _make_cohort(organisation=organisation)
        _make_cohort(organisation=organisation)
        user = UserFactory()
        assign_object_role(user, granted_cohort, "cohort_admin")

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

    def test_a_raw_guardian_permission_with_no_role_assignment_grants_nothing(
        self, mock_site_context
    ):
        """Visibility is answered from role assignments, never from guardian
        rows directly -- a guardian permission assigned by hand, with no
        matching ObjectRoleAssignment behind it, must not be enough."""
        organisation = OrganisationFactory()
        cohort = _make_cohort(organisation=organisation)
        user = UserFactory()
        assign_perm("freedom_ls_learner_management.view_cohort", user, cohort)

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
        assign_object_role(user, organisation, "organisation_admin")

        assert set(all_cohorts_visible_to(user)) == {cohort_a, cohort_b}

    def test_cohorts_in_another_organisation_are_excluded(self, mock_site_context):
        organisation = OrganisationFactory()
        mine = _make_cohort(organisation=organisation)
        _make_cohort(organisation=OrganisationFactory())
        user = UserFactory()
        assign_object_role(user, organisation, "organisation_admin")

        assert list(all_cohorts_visible_to(user)) == [mine]

    def test_guardian_grant_only_sees_the_granted_cohort(self, mock_site_context):
        organisation = OrganisationFactory()
        granted = _make_cohort(organisation=organisation)
        _make_cohort(organisation=organisation)
        user = UserFactory()
        assign_object_role(user, granted, "cohort_admin")

        assert list(all_cohorts_visible_to(user)) == [granted]

    def test_roles_in_two_organisations_are_unioned(self, mock_site_context):
        first = OrganisationFactory()
        second = OrganisationFactory()
        cohort_a = _make_cohort(organisation=first)
        cohort_b = _make_cohort(organisation=second)
        user = UserFactory()
        assign_object_role(user, first, "organisation_admin")
        assign_object_role(user, second, "organisation_admin")

        assert set(all_cohorts_visible_to(user)) == {cohort_a, cohort_b}

    def test_both_paths_return_each_cohort_once(self, mock_site_context):
        organisation = OrganisationFactory()
        cohort = _make_cohort(organisation=organisation)
        user = UserFactory()
        assign_object_role(user, organisation, "organisation_admin")
        assign_object_role(user, cohort, "cohort_admin")

        assert list(all_cohorts_visible_to(user)).count(cohort) == 1

    def test_anonymous_user_sees_no_cohorts(self, mock_site_context):
        _make_cohort()

        assert list(all_cohorts_visible_to(AnonymousUser())) == []

    def test_user_with_neither_role_nor_grant_sees_no_cohorts(self, mock_site_context):
        _make_cohort()
        user = UserFactory()

        assert list(all_cohorts_visible_to(user)) == []

    def test_it_agrees_with_cohorts_visible_to_within_one_organisation(
        self, mock_site_context
    ):
        """The two helpers must never disagree about a single cohort."""
        organisation = OrganisationFactory()
        granted = _make_cohort(organisation=organisation)
        _make_cohort(organisation=organisation)
        user = UserFactory()
        assign_object_role(user, granted, "cohort_admin")

        assert set(all_cohorts_visible_to(user)) == set(
            cohorts_visible_to(user, organisation)
        )


@pytest.mark.django_db
class TestCanViewCohort:
    """The per-object check behind the report admin's permission hooks."""

    def test_role_holder_may_view_a_cohort_in_their_organisation(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        cohort = _make_cohort(organisation=organisation)
        user = UserFactory()
        assign_object_role(user, organisation, "organisation_admin")

        assert can_view_cohort(user, cohort) is True

    def test_role_holder_may_not_view_a_cohort_in_another_organisation(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        foreign_cohort = _make_cohort(organisation=OrganisationFactory())
        user = UserFactory()
        assign_object_role(user, organisation, "organisation_admin")

        assert can_view_cohort(user, foreign_cohort) is False

    def test_guardian_grant_holder_may_view_the_granted_cohort(self, mock_site_context):
        cohort = _make_cohort()
        user = UserFactory()
        assign_object_role(user, cohort, "cohort_admin")

        assert can_view_cohort(user, cohort) is True

    def test_guardian_grant_holder_may_not_view_a_sibling_cohort(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        granted = _make_cohort(organisation=organisation)
        sibling = _make_cohort(organisation=organisation)
        user = UserFactory()
        assign_object_role(user, granted, "cohort_admin")

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
        assign_object_role(role_holder, organisation, "organisation_admin")

        assert set(learners_visible_to(role_holder, organisation)) == {learner}

    def test_inactive_learner_is_not_visible_to_an_organisation_role_holder(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        LearnerFactory(user=UserFactory(), organisation=organisation, is_active=False)
        role_holder = UserFactory()
        assign_object_role(role_holder, organisation, "organisation_admin")

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
        assign_object_role(role_holder, organisation, "organisation_admin")

        assert list(learners_visible_to(role_holder, organisation)) == []

    def test_include_removed_returns_a_removed_learner_on_the_organisation_path(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        removed = LearnerFactory(
            user=UserFactory(), organisation=organisation, is_active=False
        )
        role_holder = UserFactory()
        assign_object_role(role_holder, organisation, "organisation_admin")

        result = learners_visible_to(role_holder, organisation, include_removed=True)

        assert set(result) == {removed}

    def test_include_removed_returns_a_removed_member_on_the_cohort_grant_path(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        cohort = _make_cohort(organisation=organisation)
        removed = LearnerFactory(
            user=UserFactory(), organisation=organisation, is_active=False
        )
        CohortMembershipFactory(learner=removed, cohort=cohort)
        educator = UserFactory()
        assign_object_role(educator, cohort, "cohort_admin")

        result = learners_visible_to(educator, organisation, include_removed=True)

        assert set(result) == {removed}

    def test_learner_in_another_organisation_is_not_visible(self, mock_site_context):
        organisation = OrganisationFactory()
        LearnerFactory(user=UserFactory(), organisation=OrganisationFactory())
        role_holder = UserFactory()
        assign_object_role(role_holder, organisation, "organisation_admin")

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
        assign_object_role(educator, granted_cohort, "cohort_admin")

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
class TestActiveOrganisationAdmins:
    """Who to ask when a denied action names an organisation admin: an
    active organisation_admin whose grant and OrganisationMember are both
    still active."""

    def test_an_active_admin_with_an_active_membership_is_included(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        admin = UserFactory()
        assign_object_role(admin, organisation, "organisation_admin")

        assert list(active_organisation_admins(organisation)) == [admin]

    def test_an_inactive_user_is_excluded(self, mock_site_context):
        organisation = OrganisationFactory()
        admin = UserFactory()
        assign_object_role(admin, organisation, "organisation_admin")
        admin.is_active = False
        admin.save(update_fields=["is_active"])

        assert list(active_organisation_admins(organisation)) == []

    def test_a_removed_role_assignment_is_excluded(self, mock_site_context):
        organisation = OrganisationFactory()
        admin = UserFactory()
        assign_object_role(admin, organisation, "organisation_admin")
        remove_object_role(admin, organisation, "organisation_admin")

        assert list(active_organisation_admins(organisation)) == []

    def test_an_inactive_organisation_member_is_excluded(self, mock_site_context):
        organisation = OrganisationFactory()
        admin = UserFactory()
        assign_object_role(admin, organisation, "organisation_admin")
        OrganisationMember.objects.filter(user=admin, organisation=organisation).update(
            is_active=False
        )

        assert list(active_organisation_admins(organisation)) == []


@pytest.mark.django_db
class TestCohortEducators:
    def test_lists_a_cohort_admin_and_a_cohort_viewer_with_role_display_names(
        self, mock_site_context
    ):
        cohort = _make_cohort()
        admin = UserFactory(first_name="Ada", last_name="Admin")
        viewer = UserFactory(first_name="Vera", last_name="Viewer")
        assign_object_role(admin, cohort, "cohort_admin")
        assign_object_role(viewer, cohort, "cohort_viewer")
        roles = get_role_config(cohort.site.name)

        assert cohort_educators(cohort) == [
            (admin, roles["cohort_admin"].display_name),
            (viewer, roles["cohort_viewer"].display_name),
        ]

    def test_an_inactive_organisation_member_is_excluded(self, mock_site_context):
        cohort = _make_cohort()
        educator = UserFactory()
        assign_object_role(educator, cohort, "cohort_admin")
        OrganisationMember.objects.filter(
            user=educator, organisation=cohort.organisation
        ).update(is_active=False)

        assert cohort_educators(cohort) == []

    def test_an_inactive_assignment_is_excluded(self, mock_site_context):
        cohort = _make_cohort()
        educator = UserFactory()
        assign_object_role(educator, cohort, "cohort_admin")
        remove_object_role(educator, cohort, "cohort_admin")

        assert cohort_educators(cohort) == []

    def test_an_assignment_on_a_sibling_cohort_is_excluded(self, mock_site_context):
        organisation = OrganisationFactory()
        cohort = _make_cohort(organisation=organisation)
        sibling = _make_cohort(organisation=organisation)
        educator = UserFactory()
        assign_object_role(educator, sibling, "cohort_admin")

        assert cohort_educators(cohort) == []

    def test_a_configured_role_granting_view_cohort_is_listed(
        self, mock_site_context, mocker: MockerFixture
    ):
        """The roles come from the site config, not a hard-coded pair."""
        tutor = Role(
            display_name="Cohort tutor",
            assignment_scope=SCOPE_OBJECT,
            permissions=frozenset({"freedom_ls_learner_management.view_cohort"}),
        )
        mocker.patch(
            "freedom_ls.role_based_permissions.loader._get_role_config_cached",
            return_value=BASE_ROLES.extend({"cohort_tutor": tutor}),
        )
        cohort = _make_cohort()
        educator = UserFactory()
        assign_object_role(educator, cohort, "cohort_tutor")

        assert cohort_educators(cohort) == [(educator, "Cohort tutor")]

    def test_an_assignment_of_a_role_the_config_lacks_is_left_out(
        self, mock_site_context, mocker: MockerFixture
    ):
        cohort = _make_cohort()
        educator = UserFactory()
        assign_object_role(educator, cohort, "cohort_viewer")
        without_viewer = SiteRolesConfig(
            {key: role for key, role in BASE_ROLES.items() if key != "cohort_viewer"}
        )
        mocker.patch(
            "freedom_ls.role_based_permissions.loader._get_role_config_cached",
            return_value=without_viewer,
        )

        assert cohort_educators(cohort) == []


@pytest.mark.django_db
class TestCohortCounts:
    def test_counts_active_members_and_active_registrations(self, mock_site_context):
        cohort = _make_cohort()
        CohortMembershipFactory(
            cohort=cohort, learner=LearnerFactory(organisation=cohort.organisation)
        )
        CohortMembershipFactory(
            cohort=cohort,
            learner=LearnerFactory(organisation=cohort.organisation, is_active=False),
        )
        CohortCourseRegistrationFactory(cohort=cohort)
        CohortCourseRegistrationFactory(cohort=cohort)
        CohortCourseRegistrationFactory(cohort=cohort, is_active=False)

        assert cohort_counts(cohort) == CohortCounts(learners=1, courses=2)
        assert cohort_learner_count(cohort) == 1
        assert cohort_course_count(cohort) == 2

    def test_both_counts_cost_one_query(
        self, mock_site_context, django_assert_num_queries
    ):
        cohort = _make_cohort()

        with django_assert_num_queries(1):
            cohort_counts(cohort)

    def test_an_empty_cohort_counts_zero(self, mock_site_context):
        assert cohort_counts(_make_cohort()) == CohortCounts(learners=0, courses=0)


@pytest.mark.django_db
class TestCohortIsEmpty:
    def test_a_cohort_with_nothing_is_empty(self, mock_site_context):
        assert cohort_is_empty(_make_cohort()) is True

    def test_a_removed_learners_membership_counts(self, mock_site_context):
        cohort = _make_cohort()
        CohortMembershipFactory(
            cohort=cohort,
            learner=LearnerFactory(organisation=cohort.organisation, is_active=False),
        )

        assert cohort_is_empty(cohort) is False

    def test_an_inactive_registration_counts(self, mock_site_context):
        cohort = _make_cohort()
        CohortCourseRegistrationFactory(cohort=cohort, is_active=False)

        assert cohort_is_empty(cohort) is False

    def test_the_check_costs_one_query(
        self, mock_site_context, django_assert_num_queries
    ):
        cohort = _make_cohort()

        with django_assert_num_queries(1):
            cohort_is_empty(cohort)


@pytest.mark.django_db
class TestLearnerForCourse:
    """learner_for_course decides which Learner and registration a piece of
    work lands under. organisation_for_learner_course is a thin read of
    .learner.organisation off the same resolution, so most of its own cases
    are exercised there instead of being duplicated here."""

    def test_no_registration_returns_none(self, mock_site_context):
        course = CourseFactory()
        user = UserFactory()

        assert learner_for_course(user, course) is None

    def test_falls_back_to_individual_registration_when_no_cohort_registration(
        self, mock_site_context
    ):
        course = CourseFactory()
        user = UserFactory()
        registration = _make_registration(user, course)

        resolved = learner_for_course(user, course)

        assert resolved == ResolvedRegistration(registration.learner, registration)

    def test_cohort_registration_wins_over_an_individual_one(self, mock_site_context):
        course = CourseFactory()
        user = UserFactory()
        cohort_organisation = OrganisationFactory()
        cohort = _make_cohort(organisation=cohort_organisation)
        cohort_learner = LearnerFactory(user=user, organisation=cohort_organisation)
        CohortMembershipFactory(learner=cohort_learner, cohort=cohort)
        cohort_registration = CohortCourseRegistrationFactory(
            cohort=cohort, course=course
        )
        _make_registration(user, course, organisation=OrganisationFactory())

        resolved = learner_for_course(user, course)

        assert resolved == ResolvedRegistration(cohort_learner, cohort_registration)

    def test_cohort_branch_deterministically_picks_the_more_recent_cohort(
        self, mock_site_context
    ):
        """A learner in two cohorts that both hold an active registration for
        this course must land on the same record every time, not on whichever
        one the query planner happens to return first."""
        course = CourseFactory()
        user = UserFactory()
        organisation = OrganisationFactory()
        learner = LearnerFactory(user=user, organisation=organisation)
        older_cohort = _make_cohort(organisation=organisation)
        newer_cohort = _make_cohort(organisation=organisation)
        CohortMembershipFactory(learner=learner, cohort=older_cohort)
        CohortMembershipFactory(learner=learner, cohort=newer_cohort)
        older_registration = CohortCourseRegistrationFactory(
            cohort=older_cohort, course=course
        )
        _backdate_cohort_registration(
            older_registration, timezone.now() - timedelta(days=7)
        )
        newer_registration = CohortCourseRegistrationFactory(
            cohort=newer_cohort, course=course
        )

        first_call = learner_for_course(user, course)
        second_call = learner_for_course(user, course)

        assert first_call == ResolvedRegistration(learner, newer_registration)
        assert second_call == ResolvedRegistration(learner, newer_registration)

    def test_cross_organisation_cohort_membership_falls_through_to_individual(
        self, mock_site_context
    ):
        """CohortMembership.clean() forbids a cross-organisation membership,
        but factories never call full_clean(), so a test-built row can link a
        Learner from a foreign site into a cohort whose registration query
        still finds it. The direct Learner lookup is site-aware and excludes
        that row, so this must fall through to the individual registration
        rather than raising."""
        course = CourseFactory()
        user = UserFactory()
        outsider_organisation = OrganisationFactory(site=SiteFactory())
        outsider_learner = LearnerFactory(user=user, organisation=outsider_organisation)
        cohort = _make_cohort(organisation=OrganisationFactory())
        CohortMembershipFactory(learner=outsider_learner, cohort=cohort)
        CohortCourseRegistrationFactory(cohort=cohort, course=course)
        individual_registration = _make_registration(user, course)

        resolved = learner_for_course(user, course)

        assert resolved == ResolvedRegistration(
            individual_registration.learner, individual_registration
        )


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
        CohortCourseRegistrationFactory(cohort=cohort, course=course)
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
        CohortCourseRegistrationFactory(cohort=cohort, course=course)
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
        CohortCourseRegistrationFactory(cohort=cohort, course=course)
        for _ in range(duplicates):
            _make_registration(user, course)

        # 2, not 1: learner_for_course needs a Learner instance as well as
        # the registration, and the join from the registration back to this
        # member's Learner is a reverse relation select_related cannot
        # follow. The ceiling that matters -- that cost does not grow with
        # how many registrations the learner holds -- still holds at 2.
        with django_assert_max_num_queries(2):
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


@pytest.mark.django_db
class TestEducatorsOf:
    """The inverse of learners_visible_to, built from the same grant builders."""

    def test_educators_of_agrees_with_learners_visible_to_inside_a_request(
        self, world: World
    ) -> None:
        """Neither direction consults Cohort.is_active: an inactive cohort keeps
        its members and their educators, and loses only course access and peer
        links. If that changes, change learners_visible_to and educators_of
        together; this test fails when only one moves."""
        assert visible_pairs(world) == educator_pairs(world)

    def test_an_inactive_cohort_keeps_its_educators(self, world: World) -> None:
        Cohort.objects.filter(pk=world.cohorts["c1"].pk).update(is_active=False)

        assert visible_pairs(world) == educator_pairs(world)
        assert "c1_admin" in educator_names(world, "in_c1")

    @pytest.mark.usefixtures("without_request")
    def test_educators_of_agrees_with_learners_visible_to_outside_a_request(
        self, world: World
    ) -> None:
        assert visible_pairs(world) == educator_pairs(world)

    def test_a_superuser_with_no_role_is_in_learners_visible_to(
        self, world: World
    ) -> None:
        learner = world.learners["in_c1"]
        superuser = UserFactory(superuser=True)

        assert (
            learners_visible_to(superuser, learner.organisation)
            .filter(pk=learner.pk)
            .exists()
        )

    def test_a_superuser_with_no_role_is_not_in_educators_of(
        self, world: World
    ) -> None:
        superuser = UserFactory(superuser=True)

        assert (
            not educators_of(world.learners["in_c1"]).filter(pk=superuser.pk).exists()
        )

    def test_an_organisation_admin_is_an_educator_of_their_own_learner_row(
        self, world: World
    ) -> None:
        learner = world.learners["also_o1_admin"]

        assert educators_of(learner).filter(pk=learner.user_id).exists()

    def test_an_inactive_learner_has_no_educators(self, world: World) -> None:
        assert list(educators_of(world.learners["inactive_in_c1"])) == []

    def test_the_learners_own_user_being_inactive_does_not_remove_their_educators(
        self, world: World
    ) -> None:
        learner = world.learners["in_c1"]
        learner.user.is_active = False
        learner.user.save()

        assert "c1_admin" in educator_names(world, "in_c1")

    @pytest.mark.parametrize(
        "learner_name",
        [
            "no_cohort",
            "in_c1",
            "in_c1_and_c2",
            "in_o1_and_o2",
            "in_o1_and_o2_via_c3",
            "also_o1_admin",
        ],
    )
    def test_a_site_admin_without_an_organisation_member_row_is_an_educator_of_every_active_learner(
        self, world: World, learner_name: str
    ) -> None:
        site_admin = world.role_holders["site_admin"]
        OrganisationMember.objects.filter(user=site_admin).delete()

        assert "site_admin" in educator_names(world, learner_name)

    def test_a_site_admin_is_an_educator_of_no_learner_on_another_site(
        self, world: World
    ) -> None:
        other_site = SiteFactory()
        other_learner = LearnerFactory(
            organisation=OrganisationFactory(site=other_site)
        )

        assert (
            not educators_of(other_learner)
            .filter(pk=world.role_holders["site_admin"].pk)
            .exists()
        )

    def test_roles_narrows_to_that_subset(self, world: World) -> None:
        assert educator_names(world, "in_c1", roles=frozenset({"cohort_viewer"})) == {
            "c1_viewer",
            "c1_c2_viewer",
        }

    def test_through_cohorts_drops_a_cohort_only_educator_whose_cohort_is_not_listed(
        self, world: World
    ) -> None:
        only_c1 = Cohort.objects.filter(pk=world.cohorts["c1"].pk).values("pk")

        assert educator_names(world, "in_c1_and_c2", through_cohorts=only_c1) == {
            "site_admin",
            "o1_admin",
            "c1_admin",
            "c1_viewer",
            "c1_c2_admin",
            "c1_c2_viewer",
        }

    def test_without_organisation_and_site_branches_only_cohort_educators_remain(
        self, world: World
    ) -> None:
        assert educator_names(
            world, "in_c1_and_c2", through_organisation_and_site=False
        ) == {
            "c1_admin",
            "c1_viewer",
            "c1_c2_admin",
            "c1_c2_viewer",
            "custom_educator_c2",
        }


def _colleague_names(world: World, holder_name: str) -> set[str]:
    holder_names = {user.pk: name for name, user in world.role_holders.items()}
    pks = colleagues_of(world.role_holders[holder_name], world.site).values_list(
        "pk", flat=True
    )
    return {holder_names[pk] for pk in pks if pk in holder_names}


@pytest.mark.django_db
class TestColleaguesOf:
    def test_an_organisation_role_holder_and_a_cohort_role_holder_are_colleagues(
        self, world: World
    ) -> None:
        assert "c1_admin" in _colleague_names(world, "o1_admin")
        assert "o1_admin" in _colleague_names(world, "c1_admin")

    def test_two_cohort_role_holders_in_the_same_organisation_are_colleagues(
        self, world: World
    ) -> None:
        assert "custom_educator_c2" in _colleague_names(world, "c1_admin")

    def test_a_role_holder_in_another_organisation_is_not_a_colleague(
        self, world: World
    ) -> None:
        other_admin = UserFactory()
        assign_object_role(
            other_admin, OrganisationFactory(site=world.site), "organisation_admin"
        )

        assert (
            not colleagues_of(world.role_holders["o1_admin"], world.site)
            .filter(pk=other_admin.pk)
            .exists()
        )

    def test_a_site_admin_with_no_organisation_or_cohort_role_is_not_a_colleague(
        self, world: World
    ) -> None:
        assert "site_admin" not in _colleague_names(world, "o1_admin")

    def test_a_site_admin_has_no_colleagues(self, world: World) -> None:
        assert _colleague_names(world, "site_admin") == set()

    def test_deactivating_the_colleagues_organisation_member_removes_them(
        self, world: World
    ) -> None:
        OrganisationMember.objects.filter(user=world.role_holders["c1_admin"]).update(
            is_active=False
        )

        assert "c1_admin" not in _colleague_names(world, "o1_admin")

    def test_deactivating_the_senders_organisation_member_removes_their_colleagues(
        self, world: World
    ) -> None:
        OrganisationMember.objects.filter(user=world.role_holders["o1_admin"]).update(
            is_active=False
        )

        assert _colleague_names(world, "o1_admin") == set()

    def test_a_superuser_without_a_role_is_not_a_colleague(self, world: World) -> None:
        superuser = UserFactory(superuser=True)

        assert (
            not colleagues_of(world.role_holders["o1_admin"], world.site)
            .filter(pk=superuser.pk)
            .exists()
        )

    def test_a_holder_of_a_role_granting_nothing_is_not_a_colleague(
        self, world: World
    ) -> None:
        assert "custom_bystander_o1" not in _colleague_names(world, "o1_admin")

    def test_a_user_is_not_their_own_colleague(self, world: World) -> None:
        assert "o1_admin" not in _colleague_names(world, "o1_admin")

    def test_an_inactive_user_is_not_a_colleague(self, world: World) -> None:
        assert "c1_admin_inactive_user" not in _colleague_names(world, "o1_admin")


def _peer_names(world: World, learner_name: str) -> set[str]:
    learner_names = {learner.pk: name for name, learner in world.learners.items()}
    pks = peers_of(world.learners[learner_name]).values_list("pk", flat=True)
    return {learner_names[pk] for pk in pks if pk in learner_names}


def _register_through(
    learner: Learner, course: Course, *, through_cohort: bool
) -> None:
    if not through_cohort:
        LearnerCourseRegistrationFactory(learner=learner, course=course)
        return
    cohort = CohortFactory(organisation=learner.organisation)
    CohortMembershipFactory(cohort=cohort, learner=learner)
    CohortCourseRegistrationFactory(cohort=cohort, course=course)


@pytest.mark.django_db
class TestPeersOf:
    def test_learners_in_a_shared_cohort_are_peers(self, world: World) -> None:
        assert "in_c1_and_c2" in _peer_names(world, "in_c1")

    def test_a_learner_in_no_shared_cohort_with_no_shared_course_is_not_a_peer(
        self, world: World
    ) -> None:
        assert "also_o1_admin" not in _peer_names(world, "in_c1")

    @pytest.mark.parametrize(
        ("own_cohort_registration", "other_cohort_registration"),
        [(False, False), (False, True), (True, False), (True, True)],
        ids=[
            "individual-individual",
            "individual-cohort",
            "cohort-individual",
            "cohort-cohort",
        ],
    )
    def test_learners_registered_for_the_same_course_by_any_pair_of_paths_are_peers(
        self,
        mock_site_context: Site,
        own_cohort_registration: bool,
        other_cohort_registration: bool,
    ) -> None:
        organisation = OrganisationFactory(site=mock_site_context)
        course = LearnerCourseRegistrationFactory().course
        own = LearnerFactory(organisation=organisation)
        other = LearnerFactory(organisation=organisation)
        _register_through(own, course, through_cohort=own_cohort_registration)
        _register_through(other, course, through_cohort=other_cohort_registration)

        assert peers_of(own).filter(pk=other.pk).exists()

    def test_an_inactive_learner_has_no_peers(self, world: World) -> None:
        assert _peer_names(world, "inactive_in_c1") == set()

    def test_an_inactive_learner_is_not_a_peer(self, world: World) -> None:
        assert "inactive_in_c1" not in _peer_names(world, "in_c1")

    def test_an_inactive_registration_of_the_other_learner_makes_no_peer(
        self, world: World
    ) -> None:
        LearnerCourseRegistration.objects.filter(
            learner=world.learners["no_cohort"]
        ).update(is_active=False)

        assert "no_cohort" not in _peer_names(world, "in_c1")

    def test_an_inactive_registration_of_the_learner_makes_no_peer(
        self, world: World
    ) -> None:
        LearnerCourseRegistration.objects.filter(
            learner=world.learners["in_c1"]
        ).update(is_active=False)

        assert "no_cohort" not in _peer_names(world, "in_c1")

    def test_a_course_shared_across_two_organisations_is_not_a_peer_relationship(
        self, world: World
    ) -> None:
        peer_organisations = set(
            peers_of(world.learners["in_o1_and_o2"]).values_list(
                "organisation_id", flat=True
            )
        )

        assert world.organisations["o2"].pk not in peer_organisations

    def test_a_learner_is_not_their_own_peer(self, world: World) -> None:
        assert "in_c1" not in _peer_names(world, "in_c1")

    def test_a_learner_is_not_a_peer_of_their_other_organisation_row(
        self, world: World
    ) -> None:
        assert "in_o1_and_o2_via_c3" not in _peer_names(world, "in_o1_and_o2")

    @pytest.mark.usefixtures("without_request")
    def test_cohort_and_course_peers_are_found_outside_a_request(
        self, world: World
    ) -> None:
        assert _peer_names(world, "in_c1") >= {"in_c1_and_c2", "no_cohort"}

    def test_an_inactive_cohort_links_no_peers_through_membership_or_its_courses(
        self, world: World
    ) -> None:
        Cohort.objects.filter(pk=world.cohorts["c1"].pk).update(is_active=False)

        assert "in_c1_and_c2" not in _peer_names(world, "in_c1")
        assert "in_c1" not in _peer_names(world, "in_c1_and_c2")

    def test_a_learner_in_an_inactive_cohort_keeps_peers_found_another_way(
        self, world: World
    ) -> None:
        Cohort.objects.filter(pk=world.cohorts["c1"].pk).update(is_active=False)

        assert "no_cohort" in _peer_names(world, "in_c1")

    @pytest.mark.parametrize(
        ("own_cohort_registration", "other_cohort_registration"),
        [(False, True), (True, False), (True, True)],
        ids=["individual-cohort", "cohort-individual", "cohort-cohort"],
    )
    def test_a_course_shared_only_through_an_inactive_cohort_makes_no_peer(
        self,
        mock_site_context: Site,
        own_cohort_registration: bool,
        other_cohort_registration: bool,
    ) -> None:
        organisation = OrganisationFactory(site=mock_site_context)
        course = LearnerCourseRegistrationFactory().course
        own = LearnerFactory(organisation=organisation)
        other = LearnerFactory(organisation=organisation)
        _register_through(own, course, through_cohort=own_cohort_registration)
        _register_through(other, course, through_cohort=other_cohort_registration)
        Cohort.objects.filter(organisation=organisation).update(is_active=False)

        assert not peers_of(own).filter(pk=other.pk).exists()

    def test_peers_through_ignores_an_inactive_cohort_it_is_passed(
        self, world: World
    ) -> None:
        c1 = world.cohorts["c1"]
        Cohort.objects.filter(pk=c1.pk).update(is_active=False)
        none = Course.objects.none().values("pk")

        peers = peers_through(
            world.learners["in_c1"],
            cohorts=Cohort.objects.filter(pk=c1.pk).values("pk"),
            own_courses=none,
            cohort_courses=none,
        )

        assert not peers.exists()


@pytest.mark.django_db
class TestInactiveCohortAccess:
    @pytest.mark.parametrize(
        ("scenario", "expected"),
        [
            ("inactive_cohort_only", False),
            ("inactive_cohort_and_individual", True),
            ("inactive_cohort_and_active_cohort", True),
            ("reactivated_cohort", True),
        ],
    )
    def test_the_per_row_check_and_the_queryset_expression_agree(
        self, mock_site_context, scenario, expected
    ):
        course = CourseFactory()
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)
        cohort = _make_cohort(organisation=organisation)
        CohortMembershipFactory(learner=learner, cohort=cohort)
        CohortCourseRegistrationFactory(cohort=cohort, course=course, is_active=True)
        cohort.is_active = scenario == "reactivated_cohort"
        cohort.save()
        if scenario == "inactive_cohort_and_individual":
            LearnerCourseRegistrationFactory(
                learner=learner, course=course, is_active=True
            )
        if scenario == "inactive_cohort_and_active_cohort":
            second = _make_cohort(organisation=organisation)
            CohortMembershipFactory(learner=learner, cohort=second)
            CohortCourseRegistrationFactory(cohort=second, course=course)

        per_row = is_registered_for_course(learner.user, course)
        in_queryset = (
            Course.objects.filter(pk=course.pk)
            .annotate(_is_registered=is_registered_for_course_expression(learner.user))
            .get()
            ._is_registered
        )

        assert (per_row, in_queryset) == (expected, expected)

    def test_learner_for_course_skips_an_inactive_cohorts_registration(
        self, mock_site_context
    ):
        course = CourseFactory()
        user = UserFactory()
        organisation = OrganisationFactory()
        cohort = _make_cohort(organisation=organisation)
        cohort.is_active = False
        cohort.save()
        learner = LearnerFactory(user=user, organisation=organisation)
        CohortMembershipFactory(learner=learner, cohort=cohort)
        CohortCourseRegistrationFactory(cohort=cohort, course=course)
        individual = _make_registration(user, course, organisation=organisation)

        resolved = learner_for_course(user, course)

        assert resolved == ResolvedRegistration(individual.learner, individual)


@pytest.mark.django_db
class TestRegisterableCoursesFor:
    def test_lists_a_hidden_course(self, mock_site_context):
        cohort = _make_cohort(organisation=OrganisationFactory())
        course = CourseFactory(visibility=CourseVisibility.HIDDEN)

        assert list(registerable_courses_for(cohort)) == [course]

    def test_omits_a_coming_soon_course(self, mock_site_context):
        cohort = _make_cohort(organisation=OrganisationFactory())
        CourseFactory(visibility=CourseVisibility.COMING_SOON)

        assert list(registerable_courses_for(cohort)) == []

    def test_omits_a_course_the_cohort_actively_holds(self, mock_site_context):
        cohort = _make_cohort(organisation=OrganisationFactory())
        CohortCourseRegistrationFactory(cohort=cohort, is_active=True)

        assert list(registerable_courses_for(cohort)) == []

    def test_includes_a_course_the_cohort_holds_inactively(self, mock_site_context):
        cohort = _make_cohort(organisation=OrganisationFactory())
        registration = CohortCourseRegistrationFactory(cohort=cohort, is_active=False)

        assert list(registerable_courses_for(cohort)) == [registration.course]

    def test_includes_a_course_only_another_cohort_holds(self, mock_site_context):
        cohort = _make_cohort(organisation=OrganisationFactory())
        registration = CohortCourseRegistrationFactory(is_active=True)

        assert list(registerable_courses_for(cohort)) == [registration.course]


@pytest.mark.django_db
class TestRegisterableCoursesForLearner:
    def test_omits_a_coming_soon_course(self, mock_site_context):
        learner = LearnerFactory()
        CourseFactory(visibility=CourseVisibility.COMING_SOON)

        assert list(registerable_courses_for_learner(learner)) == []

    def test_omits_a_course_the_learner_is_actively_registered_for(
        self, mock_site_context
    ):
        learner = LearnerFactory()
        LearnerCourseRegistrationFactory(learner=learner, is_active=True)

        assert list(registerable_courses_for_learner(learner)) == []

    def test_includes_a_course_the_learner_holds_inactively(self, mock_site_context):
        learner = LearnerFactory()
        registration = LearnerCourseRegistrationFactory(
            learner=learner, is_active=False
        )

        assert list(registerable_courses_for_learner(learner)) == [registration.course]


@pytest.mark.django_db
class TestMembersKeepingAccess:
    def _scenario(self):
        organisation = OrganisationFactory()
        cohort = _make_cohort(organisation=organisation)
        course = CourseFactory()
        registration = CohortCourseRegistrationFactory(cohort=cohort, course=course)
        return organisation, cohort, course, registration

    def _member(self, organisation: Organisation, cohort: Cohort, **learner_fields):
        learner = LearnerFactory(organisation=organisation, **learner_fields)
        CohortMembershipFactory(learner=learner, cohort=cohort)
        return learner

    def test_names_a_member_kept_by_an_individual_registration(self, mock_site_context):
        organisation, cohort, course, registration = self._scenario()
        member = self._member(organisation, cohort)
        LearnerCourseRegistrationFactory(learner=member, course=course, is_active=True)

        assert list(members_keeping_access(registration)) == [member]

    def test_names_a_member_kept_by_another_active_cohort(self, mock_site_context):
        organisation, cohort, course, registration = self._scenario()
        member = self._member(organisation, cohort)
        other = _make_cohort(organisation=organisation)
        CohortMembershipFactory(learner=member, cohort=other)
        CohortCourseRegistrationFactory(cohort=other, course=course)

        assert list(members_keeping_access(registration)) == [member]

    def test_excludes_a_member_kept_only_by_an_inactive_cohorts_registration(
        self, mock_site_context
    ):
        organisation, cohort, course, registration = self._scenario()
        member = self._member(organisation, cohort)
        other = _make_cohort(organisation=organisation)
        other.is_active = False
        other.save()
        CohortMembershipFactory(learner=member, cohort=other)
        CohortCourseRegistrationFactory(cohort=other, course=course)

        assert list(members_keeping_access(registration)) == []

    def test_excludes_a_member_with_an_inactive_individual_registration(
        self, mock_site_context
    ):
        organisation, cohort, course, registration = self._scenario()
        member = self._member(organisation, cohort)
        LearnerCourseRegistrationFactory(learner=member, course=course, is_active=False)

        assert list(members_keeping_access(registration)) == []

    def test_excludes_a_removed_learner(self, mock_site_context):
        organisation, cohort, course, registration = self._scenario()
        member = self._member(organisation, cohort, is_active=False)
        LearnerCourseRegistrationFactory(learner=member, course=course, is_active=True)

        assert list(members_keeping_access(registration)) == []

    def test_costs_one_query(self, mock_site_context, django_assert_num_queries):
        organisation, cohort, course, registration = self._scenario()
        member = self._member(organisation, cohort)
        LearnerCourseRegistrationFactory(learner=member, course=course, is_active=True)
        registration = CohortCourseRegistration.objects.select_related("course").get(
            pk=registration.pk
        )

        with django_assert_num_queries(1):
            list(members_keeping_access(registration))


def _learner_with_status(status: LearnerStatus) -> Learner:
    learner = cast(
        Learner,
        LearnerFactory(
            user=UserFactory(), organisation=OrganisationFactory(), is_active=True
        ),
    )
    if status == LearnerStatus.REMOVED:
        learner.is_active = False
        learner.save(update_fields=["is_active"])
    if status == LearnerStatus.PENDING:
        learner.user.set_unusable_password()
        learner.user.save(update_fields=["password"])
    return learner


@pytest.mark.django_db
@pytest.mark.parametrize("status", list(LearnerStatus))
def test_learner_status_and_learner_status_q_agree(
    mock_site_context, status: LearnerStatus
) -> None:
    learner = _learner_with_status(status)

    assert learner_status(learner) == status
    matching = Learner.objects.filter(learner_status_q(status))
    assert list(matching) == [learner]


@pytest.mark.django_db
def test_holds_registration_without_a_site_matches_the_same_learners_as_with_it(
    mock_site_context,
) -> None:
    course = CourseFactory()
    organisation = OrganisationFactory()
    cohort = _make_cohort(organisation=organisation)
    CohortCourseRegistrationFactory(cohort=cohort, course=course, is_active=True)
    through_cohort = LearnerFactory(organisation=organisation)
    CohortMembershipFactory(cohort=cohort, learner=through_cohort)
    individual = LearnerCourseRegistrationFactory(
        learner=LearnerFactory(organisation=organisation), course=course
    ).learner
    LearnerFactory(organisation=organisation)
    site = individual.site

    without_site = Learner.objects.filter(
        holds_registration_for_any_expression(None, [str(course.pk)])
    )
    with_site = Learner.objects.filter(
        holds_registration_for_any_expression(site, Course.objects.values("pk"))
    )

    assert set(without_site) == {through_cohort, individual}
    assert set(with_site) == set(without_site)


@pytest.mark.django_db
def test_cohorts_visible_with_delete_membership_excludes_a_cohort_a_viewer_sees(
    mock_site_context,
) -> None:
    organisation = OrganisationFactory()
    viewed = _make_cohort(organisation=organisation)
    managed = _make_cohort(organisation=organisation)
    user = UserFactory()
    assign_object_role(user, viewed, "cohort_viewer")
    assign_object_role(user, managed, "cohort_admin")

    manageable = cohorts_visible_to(
        user, organisation, capability=DELETE_COHORTMEMBERSHIP
    )

    assert list(manageable) == [managed]


def _member_of(cohort: Cohort) -> Learner:
    learner = cast(Learner, LearnerFactory(organisation=cohort.organisation))
    CohortMembershipFactory(cohort=cohort, learner=learner)
    return learner


@pytest.mark.django_db
def test_other_grants_for_names_an_active_cohorts_registration(
    mock_site_context,
) -> None:
    course = CourseFactory()
    removing = _make_cohort()
    other = _make_cohort(organisation=removing.organisation)
    learner = _member_of(removing)
    CohortMembershipFactory(cohort=other, learner=learner)
    CohortCourseRegistrationFactory(cohort=other, course=course)

    assert other_grants_for(learner, course) == [other]


@pytest.mark.django_db
def test_other_grants_for_skips_an_inactive_cohort(mock_site_context) -> None:
    course = CourseFactory()
    inactive = cast(Cohort, CohortFactory(is_active=False))
    learner = _member_of(inactive)
    CohortCourseRegistrationFactory(cohort=inactive, course=course)

    assert other_grants_for(learner, course) == []


@pytest.mark.django_db
def test_other_grants_for_skips_the_excluded_cohort(mock_site_context) -> None:
    course = CourseFactory()
    cohort = _make_cohort()
    learner = _member_of(cohort)
    CohortCourseRegistrationFactory(cohort=cohort, course=course)

    assert other_grants_for(learner, course, excluding=cohort) == []


@pytest.mark.django_db
def test_courses_losing_access_lists_a_course_only_the_removed_cohort_grants(
    mock_site_context,
) -> None:
    course = CourseFactory()
    cohort = _make_cohort()
    learner = _member_of(cohort)
    CohortCourseRegistrationFactory(cohort=cohort, course=course)

    assert courses_losing_access(learner, cohort) == [course]


@pytest.mark.django_db
def test_courses_losing_access_skips_a_course_an_individual_registration_holds(
    mock_site_context,
) -> None:
    course = CourseFactory()
    cohort = _make_cohort()
    learner = _member_of(cohort)
    CohortCourseRegistrationFactory(cohort=cohort, course=course)
    LearnerCourseRegistrationFactory(learner=learner, course=course)

    assert courses_losing_access(learner, cohort) == []


@pytest.mark.django_db
def test_courses_losing_access_skips_a_course_another_active_cohort_grants(
    mock_site_context,
) -> None:
    course = CourseFactory()
    cohort = _make_cohort()
    other = _make_cohort(organisation=cohort.organisation)
    learner = _member_of(cohort)
    CohortMembershipFactory(cohort=other, learner=learner)
    CohortCourseRegistrationFactory(cohort=cohort, course=course)
    CohortCourseRegistrationFactory(cohort=other, course=course)

    assert courses_losing_access(learner, cohort) == []


@pytest.mark.django_db
def test_courses_losing_access_skips_a_course_the_added_cohort_grants(
    mock_site_context,
) -> None:
    course = CourseFactory()
    cohort = _make_cohort()
    destination = _make_cohort(organisation=cohort.organisation)
    learner = _member_of(cohort)
    CohortCourseRegistrationFactory(cohort=cohort, course=course)
    CohortCourseRegistrationFactory(cohort=destination, course=course)

    assert courses_losing_access(learner, cohort, destination) == []


@pytest.mark.django_db
def test_courses_losing_access_ignores_an_inactive_cohort_as_another_grant(
    mock_site_context,
) -> None:
    course = CourseFactory()
    cohort = _make_cohort()
    inactive = cast(
        Cohort, CohortFactory(organisation=cohort.organisation, is_active=False)
    )
    learner = _member_of(cohort)
    CohortMembershipFactory(cohort=inactive, learner=learner)
    CohortCourseRegistrationFactory(cohort=cohort, course=course)
    CohortCourseRegistrationFactory(cohort=inactive, course=course)

    assert courses_losing_access(learner, cohort) == [course]


@pytest.mark.django_db
def test_courses_losing_access_ignores_an_inactive_registration_as_another_grant(
    mock_site_context,
) -> None:
    course = CourseFactory()
    cohort = _make_cohort()
    other = _make_cohort(organisation=cohort.organisation)
    learner = _member_of(cohort)
    CohortMembershipFactory(cohort=other, learner=learner)
    CohortCourseRegistrationFactory(cohort=cohort, course=course)
    CohortCourseRegistrationFactory(cohort=other, course=course, is_active=False)

    assert courses_losing_access(learner, cohort) == [course]


@pytest.mark.django_db
def test_courses_gaining_access_skips_courses_the_learner_already_reaches(
    mock_site_context,
) -> None:
    held, granted_elsewhere, new = CourseFactory(), CourseFactory(), CourseFactory()
    cohort = _make_cohort()
    destination = _make_cohort(organisation=cohort.organisation)
    learner = _member_of(cohort)
    LearnerCourseRegistrationFactory(learner=learner, course=held)
    CohortCourseRegistrationFactory(cohort=cohort, course=granted_elsewhere)
    for course in (held, granted_elsewhere, new):
        CohortCourseRegistrationFactory(cohort=destination, course=course)

    assert courses_gaining_access(learner, destination) == [new]


def _cohorts_granting_three_courses():
    cohort = _make_cohort()
    destination = _make_cohort(organisation=cohort.organisation)
    learner = _member_of(cohort)
    for _ in range(3):
        CohortCourseRegistrationFactory(cohort=cohort, course=CourseFactory())
        CohortCourseRegistrationFactory(cohort=destination, course=CourseFactory())
    return learner, cohort, destination


@pytest.mark.django_db
def test_courses_losing_access_runs_a_fixed_number_of_queries(
    mock_site_context, django_assert_num_queries
) -> None:
    learner, cohort, destination = _cohorts_granting_three_courses()

    with django_assert_num_queries(4):
        courses_losing_access(learner, cohort, destination)


@pytest.mark.django_db
def test_courses_gaining_access_runs_a_fixed_number_of_queries(
    mock_site_context, django_assert_num_queries
) -> None:
    learner, _, destination = _cohorts_granting_three_courses()

    with django_assert_num_queries(3):
        courses_gaining_access(learner, destination)


@pytest.mark.django_db
class TestMembersOf:
    def test_includes_an_organisation_admin(self, mock_site_context):
        organisation = OrganisationFactory()
        admin = UserFactory()
        assign_object_role(admin, organisation, "organisation_admin")

        assert list(members_of(organisation)) == [admin]

    def test_includes_a_cohort_admin_on_an_active_cohort(self, mock_site_context):
        organisation = OrganisationFactory()
        admin = UserFactory()
        assign_object_role(
            admin, _make_cohort(organisation=organisation), "cohort_admin"
        )

        assert list(members_of(organisation)) == [admin]

    def test_includes_a_cohort_viewer_on_an_inactive_cohort(self, mock_site_context):
        organisation = OrganisationFactory()
        cohort = _make_cohort(organisation=organisation)
        Cohort.objects.filter(pk=cohort.pk).update(is_active=False)
        viewer = UserFactory()
        assign_object_role(viewer, cohort, "cohort_viewer")

        assert list(members_of(organisation)) == [viewer]

    def test_includes_a_suspended_member(self, mock_site_context):
        organisation = OrganisationFactory()
        admin = UserFactory()
        assign_object_role(admin, organisation, "organisation_admin")
        OrganisationMember.objects.filter(user=admin, organisation=organisation).update(
            is_active=False
        )

        assert list(members_of(organisation)) == [admin]

    def test_includes_a_turned_off_account(self, mock_site_context):
        organisation = OrganisationFactory()
        admin = UserFactory(is_active=False)
        assign_object_role(admin, organisation, "organisation_admin")

        assert list(members_of(organisation)) == [admin]

    def test_leaves_out_a_removed_assignment(self, mock_site_context):
        organisation = OrganisationFactory()
        admin = UserFactory()
        assign_object_role(admin, organisation, "organisation_admin")
        remove_object_role(admin, organisation, "organisation_admin")

        assert list(members_of(organisation)) == []

    def test_leaves_out_another_organisations_members(self, mock_site_context):
        organisation = OrganisationFactory()
        assign_object_role(UserFactory(), OrganisationFactory(), "organisation_admin")
        assign_object_role(UserFactory(), _make_cohort(), "cohort_admin")

        assert list(members_of(organisation)) == []

    def test_leaves_out_a_learner_with_no_role(self, mock_site_context):
        organisation = OrganisationFactory()
        LearnerFactory(organisation=organisation)

        assert list(members_of(organisation)) == []

    def test_leaves_out_a_site_admin_with_no_organisation_role(self, mock_site_context):
        organisation = OrganisationFactory()
        assign_site_role(UserFactory(), "site_admin", site=mock_site_context)

        assert list(members_of(organisation)) == []

    def test_leaves_out_a_superuser_with_no_organisation_role(self, mock_site_context):
        organisation = OrganisationFactory()
        UserFactory(superuser=True)

        assert list(members_of(organisation)) == []

    def test_returns_a_user_holding_several_roles_once(self, mock_site_context):
        organisation = OrganisationFactory()
        user = UserFactory(superuser=True)
        assign_object_role(user, organisation, "organisation_admin")
        assign_object_role(
            user, _make_cohort(organisation=organisation), "cohort_viewer"
        )

        assert list(members_of(organisation)) == [user]


@pytest.mark.django_db
class TestSiteLevelAdmins:
    def test_holds_superusers_and_active_site_admins(self, mock_site_context):
        superuser = UserFactory(superuser=True)
        site_admin = UserFactory()
        assign_site_role(site_admin, "site_admin", site=mock_site_context)

        assert set(site_level_admins(mock_site_context)) == {superuser, site_admin}

    def test_leaves_out_an_inactive_site_admin_grant(self, mock_site_context):
        holder = UserFactory()
        assign_site_role(holder, "site_admin", site=mock_site_context)
        SiteRoleAssignment.objects.filter(user=holder).update(is_active=False)

        assert list(site_level_admins(mock_site_context)) == []

    def test_leaves_out_another_sites_admin(self, mock_site_context):
        other_site = SiteFactory()
        assign_site_role(UserFactory(), "site_admin", site=other_site)

        assert list(site_level_admins(mock_site_context)) == []

    def test_leaves_out_an_organisation_admin(self, mock_site_context):
        assign_object_role(UserFactory(), OrganisationFactory(), "organisation_admin")

        assert list(site_level_admins(mock_site_context)) == []


@pytest.mark.django_db
def test_registered_course_pairs_include_an_active_individual_registration(
    mock_site_context,
) -> None:
    registration = LearnerCourseRegistrationFactory()
    learner = registration.learner

    pairs = registered_course_pairs(learner.site_id, [learner.user_id])

    assert pairs == {(learner.user_id, registration.course_id)}


@pytest.mark.django_db
def test_registered_course_pairs_include_an_active_cohort_registration_for_an_active_member(
    mock_site_context,
) -> None:
    membership = CohortMembershipFactory()
    registration = CohortCourseRegistrationFactory(cohort=membership.cohort)
    learner = membership.learner

    pairs = registered_course_pairs(learner.site_id, [learner.user_id])

    assert pairs == {(learner.user_id, registration.course_id)}


@pytest.mark.django_db
def test_registered_course_pairs_skip_an_inactive_individual_registration(
    mock_site_context,
) -> None:
    learner = LearnerFactory()
    LearnerCourseRegistrationFactory(learner=learner, is_active=False)

    assert registered_course_pairs(learner.site_id, [learner.user_id]) == set()


@pytest.mark.django_db
def test_registered_course_pairs_skip_an_inactive_learner(mock_site_context) -> None:
    learner = LearnerFactory(is_active=False)
    LearnerCourseRegistrationFactory(learner=learner)

    assert registered_course_pairs(learner.site_id, [learner.user_id]) == set()


@pytest.mark.django_db
def test_registered_course_pairs_skip_an_inactive_cohort(mock_site_context) -> None:
    membership = CohortMembershipFactory()
    CohortCourseRegistrationFactory(cohort=membership.cohort)
    Cohort.objects.filter(pk=membership.cohort_id).update(is_active=False)
    learner = membership.learner

    assert registered_course_pairs(learner.site_id, [learner.user_id]) == set()


@pytest.mark.django_db
def test_registered_course_pairs_skip_an_inactive_cohort_registration(
    mock_site_context,
) -> None:
    membership = CohortMembershipFactory()
    CohortCourseRegistrationFactory(cohort=membership.cohort, is_active=False)
    learner = membership.learner

    assert registered_course_pairs(learner.site_id, [learner.user_id]) == set()


@pytest.mark.django_db
def test_registered_course_pairs_name_only_the_active_member_of_a_shared_cohort(
    mock_site_context,
) -> None:
    cohort = CohortFactory()
    active_member = CohortMembershipFactory(cohort=cohort).learner
    unrelated_member = CohortMembershipFactory(cohort=cohort).learner
    removed = CohortMembershipFactory(
        cohort=cohort,
        learner=LearnerFactory(
            user=active_member.user, organisation=OrganisationFactory(), is_active=False
        ),
    ).learner
    registration = CohortCourseRegistrationFactory(cohort=cohort)

    pairs = registered_course_pairs(
        cohort.site_id, [active_member.user_id, removed.user_id]
    )

    assert pairs == {(active_member.user_id, registration.course_id)}
    assert unrelated_member.user_id not in {user_id for user_id, _ in pairs}


@pytest.mark.django_db
def test_registered_course_pairs_skip_another_sites_registrations(
    mock_site_context,
) -> None:
    other_site = SiteFactory()
    with site_context(other_site):
        registration = LearnerCourseRegistrationFactory()
        other_learner = registration.learner

    assert (
        registered_course_pairs(mock_site_context.pk, [other_learner.user_id]) == set()
    )


@pytest.mark.django_db
def test_registered_course_pairs_are_the_same_with_and_without_an_ambient_request(
    mock_site_context,
) -> None:
    learner = LearnerCourseRegistrationFactory().learner
    with_request = registered_course_pairs(learner.site_id, [learner.user_id])

    drop_ambient_request()

    assert registered_course_pairs(learner.site_id, [learner.user_id]) == with_request
    assert with_request


@pytest.mark.django_db
def test_registered_course_pairs_narrow_to_the_given_courses(mock_site_context) -> None:
    learner = LearnerFactory()
    wanted = LearnerCourseRegistrationFactory(learner=learner)
    LearnerCourseRegistrationFactory(learner=learner)
    membership = CohortMembershipFactory(learner=learner)
    CohortCourseRegistrationFactory(cohort=membership.cohort)

    pairs = registered_course_pairs(
        learner.site_id, [learner.user_id], [wanted.course_id]
    )

    assert pairs == {(learner.user_id, wanted.course_id)}
