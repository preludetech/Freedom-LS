"""The educator's own conversation with a learner."""

from __future__ import annotations

from typing import cast

import pytest

from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.comms.factories import ConversationFactory
from freedom_ls.comms.messaging_policy import (
    MessagingDecision,
    MessagingPolicy,
    MessagingRefusal,
)
from freedom_ls.comms.models import Conversation
from freedom_ls.educator_interface.messaging import (
    own_conversation_with,
)
from freedom_ls.learner_management.factories import (
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
