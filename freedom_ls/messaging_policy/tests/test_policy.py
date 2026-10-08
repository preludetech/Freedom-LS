"""LayeredMessagingPolicy: the refusals that do not depend on any relationship."""

from __future__ import annotations

import pytest

from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.comms.messaging_policy import MessagingRefusal
from freedom_ls.messaging_policy.policy import LayeredMessagingPolicy

pytestmark = pytest.mark.django_db


@pytest.fixture
def policy() -> LayeredMessagingPolicy:
    return LayeredMessagingPolicy()


def test_a_user_cannot_message_themselves(
    policy: LayeredMessagingPolicy, mock_site_context: Site
) -> None:
    user = UserFactory()

    decision = policy.can_start(sender=user, recipient=user, site=mock_site_context)

    assert decision.reason == MessagingRefusal.SAME_USER


def test_an_inactive_sender_is_refused(
    policy: LayeredMessagingPolicy, mock_site_context: Site
) -> None:
    sender = UserFactory(is_active=False)

    decision = policy.can_start(
        sender=sender, recipient=UserFactory(), site=mock_site_context
    )

    assert decision.reason == MessagingRefusal.INACTIVE_USER


def test_an_inactive_recipient_is_refused(
    policy: LayeredMessagingPolicy, mock_site_context: Site
) -> None:
    recipient = UserFactory(is_active=False)

    decision = policy.can_start(
        sender=UserFactory(), recipient=recipient, site=mock_site_context
    )

    assert decision.reason == MessagingRefusal.INACTIVE_USER


def test_two_unrelated_users_have_no_relationship(
    policy: LayeredMessagingPolicy, mock_site_context: Site
) -> None:
    decision = policy.can_start(
        sender=UserFactory(), recipient=UserFactory(), site=mock_site_context
    )

    assert decision.reason == MessagingRefusal.NO_RELATIONSHIP


def test_nobody_is_a_candidate_recipient(
    policy: LayeredMessagingPolicy, mock_site_context: Site
) -> None:
    UserFactory()

    assert (
        list(policy.recipients_for(sender=UserFactory(), site=mock_site_context)) == []
    )


def test_reply_between_unrelated_users_returns_the_sender_direction_refusal(
    policy: LayeredMessagingPolicy, mock_site_context: Site
) -> None:
    sender = UserFactory(is_active=False)

    decision = policy.can_reply(
        sender=sender,
        recipient=UserFactory(),
        site=mock_site_context,
        conversation=sender,
    )

    assert decision.reason == MessagingRefusal.INACTIVE_USER
