"""The educator's own conversation with a learner."""

from __future__ import annotations

from typing import cast

import pytest

from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.comms.factories import ConversationFactory, MessageFactory
from freedom_ls.comms.messaging_policy import (
    MessagingDecision,
    MessagingPolicy,
    MessagingRefusal,
)
from freedom_ls.comms.models import Conversation
from freedom_ls.educator_interface.messaging import (
    oversight_conversations_for,
    own_conversation_with,
)
from freedom_ls.learner_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Cohort, Learner
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.utils import deactivate_object_role
from freedom_ls.tests.factories import SiteFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _site_context(mock_site_context):
    """Every test here builds site-aware objects and assigns roles."""


class ClosedPolicy(MessagingPolicy):
    def can_start(self, *, sender, recipient, site):
        return MessagingDecision.refuse(MessagingRefusal.CLOSED_BY_CONFIGURATION)

    def can_reply(self, *, sender, recipient, site, conversation):
        return MessagingDecision.refuse(MessagingRefusal.CLOSED_BY_CONFIGURATION)

    def recipients_for(self, *, sender, site):
        return User.objects.none()


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


def test_own_conversation_with_returns_the_shared_conversation_and_the_reply_decision(
    site_aware_request,
):
    organisation = OrganisationFactory()
    educator = _educator(organisation)
    learner = _learner(organisation)
    conversation = _conversation(educator, learner.user)
    request = site_aware_request.get("/")
    request.user = educator

    own = own_conversation_with(request, learner)

    assert own.conversation == conversation
    assert own.allowed is True


def test_own_conversation_with_returns_none_and_the_start_decision_before_a_first_message(
    site_aware_request,
):
    organisation = OrganisationFactory()
    educator = _educator(organisation)
    learner = _learner(organisation)
    request = site_aware_request.get("/")
    request.user = educator

    own = own_conversation_with(request, learner)

    assert own.conversation is None
    assert own.allowed is True


def test_own_conversation_with_is_not_allowed_when_the_policy_refuses(
    site_aware_request, settings
):
    settings.MESSAGING_POLICY = (
        "freedom_ls.educator_interface.tests.test_messaging.ClosedPolicy"
    )
    organisation = OrganisationFactory()
    educator = _educator(organisation)
    learner = _learner(organisation)
    request = site_aware_request.get("/")
    request.user = educator

    own = own_conversation_with(request, learner)

    assert own.conversation is None
    assert own.allowed is False


class TestOversightConversationsFor:
    def test_it_includes_conversations_with_a_cohort_admin_and_an_organisation_admin(
        self,
    ):
        organisation = OrganisationFactory()
        learner = _learner(organisation)
        cohort = CohortFactory(organisation=organisation)
        CohortMembershipFactory(cohort=cohort, learner=learner)
        cohort_admin = cast(User, UserFactory())
        _grant(cohort_admin, "cohort_admin", cohort)
        organisation_admin = _educator(organisation)
        with_cohort_admin = _conversation(cohort_admin, learner.user)
        with_organisation_admin = _conversation(organisation_admin, learner.user)

        found = set(oversight_conversations_for(learner))

        assert found == {with_cohort_admin, with_organisation_admin}

    def test_it_excludes_a_conversation_with_a_peer(self):
        organisation = OrganisationFactory()
        learner = _learner(organisation)
        _conversation(_learner(organisation).user, learner.user)

        assert not oversight_conversations_for(learner).exists()

    def test_it_excludes_a_conversation_with_an_educator_who_lost_the_role(self):
        organisation = OrganisationFactory()
        learner = _learner(organisation)
        cohort = CohortFactory(organisation=organisation)
        CohortMembershipFactory(cohort=cohort, learner=learner)
        former = cast(User, UserFactory())
        _grant(former, "cohort_admin", cohort)
        _conversation(former, learner.user)
        deactivate_object_role(former, cohort, "cohort_admin")

        assert not oversight_conversations_for(learner).exists()

    def test_it_excludes_a_conversation_between_the_educator_and_someone_else(self):
        organisation = OrganisationFactory()
        learner = _learner(organisation)
        educator = _educator(organisation)
        _conversation(educator, _learner(organisation).user)

        assert not oversight_conversations_for(learner).exists()

    def test_it_excludes_a_conversation_with_a_user_of_another_site(self):
        organisation = OrganisationFactory()
        learner = _learner(organisation)
        outsider = cast(User, UserFactory(site=SiteFactory()))
        _conversation(outsider, learner.user)

        assert not oversight_conversations_for(learner).exists()

    def test_it_is_empty_for_a_deactivated_learner(self):
        organisation = OrganisationFactory()
        learner = _learner(organisation)
        _conversation(_educator(organisation), learner.user)
        learner.is_active = False
        learner.save()

        assert not oversight_conversations_for(learner).exists()

    def test_it_carries_the_excerpt_and_the_prefetched_educator_newest_first(
        self, django_assert_num_queries
    ):
        organisation = OrganisationFactory()
        learner = _learner(organisation)
        older_educator = _educator(organisation)
        newer_educator = _educator(organisation)
        older = _conversation(older_educator, learner.user)
        newer = _conversation(newer_educator, learner.user)
        MessageFactory(conversation=older, sender=older_educator, body="first words")
        MessageFactory(conversation=newer, sender=newer_educator, body="latest words")

        rows = list(oversight_conversations_for(learner))

        assert rows == [newer, older]
        assert [c.last_message_body for c in rows] == ["latest words", "first words"]
        with django_assert_num_queries(0):
            assert [c.other_participants[0].user for c in rows] == [
                newer_educator,
                older_educator,
            ]
