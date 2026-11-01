"""The header Messages button under the shipped LayeredMessagingPolicy: a
learner sees it only when some organisation they belong to lets them reach an
educator, and an organisation admin only when their organisation has a learner."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import pytest

from django.contrib.sites.models import Site
from django.db.models import Model
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.learner_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
    OrganisationMemberFactory,
)
from freedom_ls.learner_management.models import Learner
from freedom_ls.messaging_policy.factories import OrganisationMessagingConfigFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role

MESSAGES_MARKER = 'aria-labelledby="messages-button-label"'

LoggedInClient = Callable[[User], Client]


def learner_with_a_cohort_admin(user: User, organisation: Model) -> Learner:
    """A Learner for ``user`` in a cohort of ``organisation`` that has an active
    cohort_admin: the one route the shipped policy flags leave open."""
    learner = cast("Learner", LearnerFactory(user=user, organisation=organisation))
    cohort = CohortFactory(organisation=organisation)
    CohortMembershipFactory(cohort=cohort, learner=learner)
    assign_object_role(UserFactory(), cohort, "cohort_admin")
    return learner


@pytest.mark.django_db
class TestMessagesButtonUnderTheShippedPolicy:
    def test_a_learner_who_can_reach_a_cohort_admin_sees_the_button(
        self, mock_site_context: Site, logged_in_client: LoggedInClient
    ) -> None:
        user = UserFactory()
        learner_with_a_cohort_admin(user, OrganisationFactory())

        response = logged_in_client(user).get(reverse("learner_interface:dashboard"))

        assert MESSAGES_MARKER in response.content.decode()

    def test_a_learner_whose_organisation_closed_learner_to_educator_sees_no_button(
        self, mock_site_context: Site, logged_in_client: LoggedInClient
    ) -> None:
        user = UserFactory()
        learner = learner_with_a_cohort_admin(user, OrganisationFactory())
        OrganisationMessagingConfigFactory(
            organisation=learner.organisation, learner_to_educator="closed"
        )

        response = logged_in_client(user).get(reverse("learner_interface:dashboard"))

        assert MESSAGES_MARKER not in response.content.decode()

    def test_a_learner_sees_the_button_when_any_organisation_is_open(
        self, mock_site_context: Site, logged_in_client: LoggedInClient
    ) -> None:
        user = UserFactory()
        closed_org = OrganisationFactory()
        open_org = OrganisationFactory()
        learner_with_a_cohort_admin(user, closed_org)
        OrganisationMessagingConfigFactory(
            organisation=closed_org, learner_to_educator="closed"
        )
        learner_with_a_cohort_admin(user, open_org)

        response = logged_in_client(user).get(reverse("learner_interface:dashboard"))

        assert MESSAGES_MARKER in response.content.decode()

    def test_an_organisation_admin_with_a_learner_row_sees_the_button(
        self, mock_site_context: Site, logged_in_client: LoggedInClient
    ) -> None:
        user = UserFactory()
        organisation = OrganisationFactory()
        OrganisationMemberFactory(user=user, organisation=organisation)
        assign_object_role(user, organisation, "organisation_admin")
        LearnerFactory(user=user, organisation=organisation)
        LearnerFactory(organisation=organisation)

        response = logged_in_client(user).get(reverse("learner_interface:dashboard"))

        assert MESSAGES_MARKER in response.content.decode()
