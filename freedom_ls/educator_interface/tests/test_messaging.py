"""Which of an educator's conversations belong to an organisation's section."""

from __future__ import annotations

from typing import cast

import pytest

from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.comms.factories import ConversationFactory
from freedom_ls.comms.models import Conversation
from freedom_ls.educator_interface.messaging import conversations_in_organisation
from freedom_ls.learner_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Cohort, Learner
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _site_context(mock_site_context):
    """Every test here builds site-aware objects and assigns roles."""


def _grant(user: User, role: str, target: Organisation | Cohort | Site) -> None:
    """Give `user` a role on `target`, granted by a superuser."""
    grantor = cast(User, UserFactory(superuser=True))
    assign_role(grantor, user, role, target)


def _learner(organisation: Organisation) -> Learner:
    return cast(Learner, LearnerFactory(organisation=organisation))


def _conversation(user: User, other: User) -> Conversation:
    return cast(Conversation, ConversationFactory(between=(user, other)))


def _educator(organisation: Organisation) -> User:
    educator = cast(User, UserFactory(staff=True))
    _grant(educator, "organisation_admin", organisation)
    return educator


def test_lists_the_educators_conversations_with_a_visible_learner():
    organisation = OrganisationFactory()
    educator = _educator(organisation)
    conversation = _conversation(educator, _learner(organisation).user)

    assert list(conversations_in_organisation(educator, organisation)) == [conversation]


def test_leaves_out_a_conversation_with_a_learner_of_another_organisation():
    organisation = OrganisationFactory()
    educator = _educator(organisation)
    _conversation(educator, _learner(OrganisationFactory()).user)

    assert not conversations_in_organisation(educator, organisation).exists()


def test_leaves_out_conversations_between_other_people():
    organisation = OrganisationFactory()
    educator = _educator(organisation)
    colleague = _educator(organisation)
    _conversation(colleague, _learner(organisation).user)

    assert not conversations_in_organisation(educator, organisation).exists()


def test_leaves_out_a_conversation_with_another_educator():
    organisation = OrganisationFactory()
    educator = _educator(organisation)
    _conversation(educator, _educator(organisation))

    assert not conversations_in_organisation(educator, organisation).exists()


def test_a_cohort_viewer_does_not_see_a_conversation_with_a_learner_outside_their_cohort():
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    cohort_educator = cast(User, UserFactory(staff=True))
    _grant(cohort_educator, "cohort_admin", cohort)
    learner = _learner(organisation)
    CohortMembershipFactory(cohort=cohort, learner=_learner(organisation))
    _conversation(cohort_educator, learner.user)

    assert not conversations_in_organisation(cohort_educator, organisation).exists()


def test_a_cohort_viewer_sees_a_conversation_with_a_learner_in_their_cohort():
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    cohort_educator = cast(User, UserFactory(staff=True))
    _grant(cohort_educator, "cohort_admin", cohort)
    learner = _learner(organisation)
    CohortMembershipFactory(cohort=cohort, learner=learner)
    conversation = _conversation(cohort_educator, learner.user)

    assert list(conversations_in_organisation(cohort_educator, organisation)) == [
        conversation
    ]


def test_a_cohort_viewer_does_not_see_a_cohort_admins_conversation_with_the_same_learner():
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    learner = _learner(organisation)
    CohortMembershipFactory(cohort=cohort, learner=learner)
    admin = cast(User, UserFactory(staff=True))
    _grant(admin, "cohort_admin", cohort)
    viewer = cast(User, UserFactory(staff=True))
    _grant(viewer, "cohort_viewer", cohort)
    _conversation(admin, learner.user)

    assert not conversations_in_organisation(viewer, organisation).exists()


def test_a_conversation_whose_learner_was_deleted_is_left_out():
    organisation = OrganisationFactory()
    educator = _educator(organisation)
    learner = _learner(organisation)
    _conversation(educator, learner.user)
    learner.user.delete()

    assert not conversations_in_organisation(educator, organisation).exists()


def test_keeps_the_inbox_annotations():
    organisation = OrganisationFactory()
    educator = _educator(organisation)
    _conversation(educator, _learner(organisation).user)

    conversation = conversations_in_organisation(educator, organisation).get()

    assert conversation.is_unread is False
