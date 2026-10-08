"""LayeredMessagingPolicy: the refusals that do not depend on any relationship,
and the educator of a learner relationship."""

from __future__ import annotations

import pytest

from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.comms.messaging_policy import MessagingRefusal
from freedom_ls.learner_management.tests.scenario_world import World
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


def test_an_educator_may_start_with_a_learner_they_can_see(
    policy: LayeredMessagingPolicy, world: World
) -> None:
    decision = policy.can_start(
        sender=world.role_holders["c1_admin"],
        recipient=world.learners["in_c1"].user,
        site=world.site,
    )

    assert decision.allowed is True


def test_a_learner_may_reply_to_their_educator(
    policy: LayeredMessagingPolicy, world: World
) -> None:
    learner = world.learners["in_c1"]

    decision = policy.can_reply(
        sender=learner.user,
        recipient=world.role_holders["c1_admin"],
        site=world.site,
        conversation=learner,
    )

    assert decision.allowed is True


def test_a_superuser_with_no_role_may_start_with_nobody(
    policy: LayeredMessagingPolicy, world: World
) -> None:
    decision = policy.can_start(
        sender=UserFactory(superuser=True),
        recipient=world.learners["in_c1"].user,
        site=world.site,
    )

    assert decision.reason == MessagingRefusal.NO_RELATIONSHIP


def test_a_reply_from_an_educator_whose_role_was_removed_is_refused(
    policy: LayeredMessagingPolicy, world: World
) -> None:
    learner = world.learners["in_c1"]

    decision = policy.can_reply(
        sender=world.role_holders["c1_admin_inactive_assignment"],
        recipient=learner.user,
        site=world.site,
        conversation=learner,
    )

    assert decision.reason == MessagingRefusal.NO_RELATIONSHIP


def test_a_reply_from_a_learner_to_an_educator_whose_role_was_removed_is_refused(
    policy: LayeredMessagingPolicy, world: World
) -> None:
    learner = world.learners["in_c1"]

    decision = policy.can_reply(
        sender=learner.user,
        recipient=world.role_holders["c1_admin_inactive_assignment"],
        site=world.site,
        conversation=learner,
    )

    assert decision.reason == MessagingRefusal.NO_RELATIONSHIP


def test_recipients_for_a_cohort_admin_are_the_users_of_the_active_learners_in_their_cohort(
    policy: LayeredMessagingPolicy, world: World
) -> None:
    recipients = policy.recipients_for(
        sender=world.role_holders["c1_admin"], site=world.site
    )

    assert set(recipients) == {
        world.learners["in_c1"].user,
        world.learners["in_c1_and_c2"].user,
    }


def test_recipients_for_exclude_the_sender(
    policy: LayeredMessagingPolicy, world: World
) -> None:
    sender = world.learners["also_o1_admin"].user

    recipients = policy.recipients_for(sender=sender, site=world.site)

    assert sender not in recipients


def test_recipients_for_exclude_a_user_who_is_inactive(
    policy: LayeredMessagingPolicy, world: World
) -> None:
    learner = world.learners["in_c1"]
    learner.user.is_active = False
    learner.user.save()

    recipients = policy.recipients_for(
        sender=world.role_holders["c1_admin"], site=world.site
    )

    assert learner.user not in recipients


def test_recipients_for_exclude_a_user_from_another_site(
    policy: LayeredMessagingPolicy, world: World
) -> None:
    learner = world.learners["in_c1"]
    User.objects.filter(pk=learner.user_id).update(site=SiteFactory())

    recipients = policy.recipients_for(
        sender=world.role_holders["site_admin"], site=world.site
    )

    assert learner.user not in recipients
