"""LayeredMessagingPolicy: the refusals that do not depend on any relationship,
the educator of a learner relationship, the colleague relationship and the
cohort-peer candidates resolved through the settings layer."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from pytest_django.fixtures import DjangoAssertNumQueries, SettingsWrapper

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.comms.messaging_policy import MessagingRefusal
from freedom_ls.learner_management.factories import (
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.tests.scenario_world import (
    World,
    build_world,
    custom_role_config,
)
from freedom_ls.messaging_policy.policy import LayeredMessagingPolicy
from freedom_ls.messaging_policy.tests.messaging_world import (
    allowed_pairs,
    recipients_pairs,
)

pytestmark = pytest.mark.django_db


ALL_CLOSED = {
    "learner_to_educator": "closed",
    "learner_to_cohort_peer": "closed",
    "learner_to_course_peer": "closed",
}


@pytest.fixture
def policy(settings: SettingsWrapper) -> LayeredMessagingPolicy:
    """The policy with the settings layer pinned, so no test depends on the shipped defaults."""
    settings.MESSAGING_DEFAULT_FLAGS = ALL_CLOSED
    settings.MESSAGING_OFFERED_EDUCATOR_ROLES = ["cohort_admin"]
    return LayeredMessagingPolicy()


@pytest.fixture
def out_of_the_box_policy() -> LayeredMessagingPolicy:
    """The policy under whatever the shipped settings are."""
    return LayeredMessagingPolicy()


QUERIES_RECIPIENTS = 3
QUERIES_ALLOWED = 3
QUERIES_CLOSED = 5
QUERIES_NO_RELATIONSHIP = 5


def open_cohort_peers(settings: SettingsWrapper) -> None:
    settings.MESSAGING_DEFAULT_FLAGS = {**ALL_CLOSED, "learner_to_cohort_peer": "open"}


@pytest.fixture(params=[1, 5])
def scaled_world(
    request: pytest.FixtureRequest, mock_site_context: Site, settings: SettingsWrapper
) -> Iterator[World]:
    with custom_role_config(mock_site_context, settings):
        yield build_world(mock_site_context, scale=request.param)


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


def test_recipients_for_a_cohort_admin_include_the_users_of_the_active_learners_in_their_cohort(
    policy: LayeredMessagingPolicy, world: World
) -> None:
    recipients = policy.recipients_for(
        sender=world.role_holders["c1_admin"], site=world.site
    )

    assert {
        world.learners["in_c1"].user,
        world.learners["in_c1_and_c2"].user,
    } <= set(recipients)


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


def test_colleagues_may_start_with_each_other_out_of_the_box(
    policy: LayeredMessagingPolicy, world: World
) -> None:
    decision = policy.can_start(
        sender=world.role_holders["c1_admin"],
        recipient=world.role_holders["o1_admin"],
        site=world.site,
    )

    assert decision.allowed is True


def test_recipients_for_an_organisation_admin_includes_a_cohort_viewer_of_the_organisation(
    policy: LayeredMessagingPolicy, world: World
) -> None:
    recipients = policy.recipients_for(
        sender=world.role_holders["o1_admin"], site=world.site
    )

    assert world.role_holders["c1_viewer"] in recipients


def test_a_learner_starting_with_a_cohort_peer_is_closed_by_configuration_out_of_the_box(
    out_of_the_box_policy: LayeredMessagingPolicy, world: World
) -> None:
    decision = out_of_the_box_policy.can_start(
        sender=world.learners["in_c1"].user,
        recipient=world.learners["in_c1_and_c2"].user,
        site=world.site,
    )

    assert decision.reason == MessagingRefusal.CLOSED_BY_CONFIGURATION


def test_a_learner_may_start_with_a_cohort_peer_when_the_flag_is_open(
    policy: LayeredMessagingPolicy, world: World, settings: SettingsWrapper
) -> None:
    open_cohort_peers(settings)

    decision = policy.can_start(
        sender=world.learners["in_c1"].user,
        recipient=world.learners["in_c1_and_c2"].user,
        site=world.site,
    )

    assert decision.allowed is True


def test_a_learner_is_refused_a_cohort_peer_when_the_flag_is_closed(
    policy: LayeredMessagingPolicy, world: World
) -> None:
    decision = policy.can_start(
        sender=world.learners["in_c1"].user,
        recipient=world.learners["in_c1_and_c2"].user,
        site=world.site,
    )

    assert decision.reason == MessagingRefusal.CLOSED_BY_CONFIGURATION


def test_a_learner_with_no_shared_cohort_has_no_relationship_even_when_the_flag_is_open(
    policy: LayeredMessagingPolicy, world: World, settings: SettingsWrapper
) -> None:
    open_cohort_peers(settings)

    decision = policy.can_start(
        sender=world.learners["no_cohort"].user,
        recipient=world.learners["in_c1"].user,
        site=world.site,
    )

    assert decision.reason == MessagingRefusal.NO_RELATIONSHIP


def test_a_removed_sender_learner_row_has_no_relationship(
    policy: LayeredMessagingPolicy, world: World, settings: SettingsWrapper
) -> None:
    open_cohort_peers(settings)
    sender = world.learners["in_c1"]
    sender.delete()

    decision = policy.can_start(
        sender=sender.user,
        recipient=world.learners["in_c1_and_c2"].user,
        site=world.site,
    )

    assert decision.reason == MessagingRefusal.NO_RELATIONSHIP


def test_recipients_for_include_a_cohort_peer_only_when_the_flag_is_open(
    policy: LayeredMessagingPolicy, world: World, settings: SettingsWrapper
) -> None:
    sender = world.learners["in_c1"].user
    peer = world.learners["in_c1_and_c2"].user
    closed = policy.recipients_for(sender=sender, site=world.site)
    open_cohort_peers(settings)
    opened = policy.recipients_for(sender=sender, site=world.site)

    assert (peer in closed, peer in opened) == (False, True)


@pytest.mark.parametrize("flag", ["open", "closed"])
def test_recipients_for_and_can_start_agree_on_every_pair(
    policy: LayeredMessagingPolicy,
    world: World,
    settings: SettingsWrapper,
    flag: str,
) -> None:
    settings.MESSAGING_DEFAULT_FLAGS = {**ALL_CLOSED, "learner_to_cohort_peer": flag}

    assert recipients_pairs(world, policy) == allowed_pairs(world, policy)


def test_a_recipient_reached_by_several_paths_is_listed_once(
    policy: LayeredMessagingPolicy, world: World, settings: SettingsWrapper
) -> None:
    open_cohort_peers(settings)
    sender = world.role_holders["c1_admin"]
    recipient = world.role_holders["o1_admin"]
    organisation = world.organisations["o1"]
    for user in (sender, recipient):
        CohortMembershipFactory(
            cohort=world.cohorts["c1"],
            learner=LearnerFactory(user=user, organisation=organisation),
        )

    recipients = list(policy.recipients_for(sender=sender, site=world.site))

    assert recipients.count(recipient) == 1


def test_recipients_for_stays_composable_without_distinct(
    policy: LayeredMessagingPolicy, world: World
) -> None:
    """The queryset must stay composable for the composer, which a distinct() would break."""
    recipients = policy.recipients_for(
        sender=world.learners["in_c1"].user, site=world.site
    )

    assert "DISTINCT" not in str(recipients.query)


def _warm_content_types(world: World) -> None:
    ContentType.objects.get_for_model(world.cohorts["c1"])
    ContentType.objects.get_for_model(world.organisations["o1"])


def test_recipients_for_runs_a_fixed_number_of_queries_whatever_the_world_size(
    policy: LayeredMessagingPolicy,
    scaled_world: World,
    settings: SettingsWrapper,
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    open_cohort_peers(settings)
    _warm_content_types(scaled_world)
    sender = scaled_world.learners["in_c1"].user

    with django_assert_num_queries(QUERIES_RECIPIENTS):
        list(policy.recipients_for(sender=sender, site=scaled_world.site))


def test_can_start_runs_a_fixed_number_of_queries_for_an_allowed_pair(
    policy: LayeredMessagingPolicy,
    scaled_world: World,
    settings: SettingsWrapper,
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    open_cohort_peers(settings)
    _warm_content_types(scaled_world)

    with django_assert_num_queries(QUERIES_ALLOWED):
        policy.can_start(
            sender=scaled_world.learners["in_c1"].user,
            recipient=scaled_world.learners["in_c1_and_c2"].user,
            site=scaled_world.site,
        )


def test_can_start_runs_a_fixed_number_of_queries_for_a_closed_pair(
    policy: LayeredMessagingPolicy,
    scaled_world: World,
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    _warm_content_types(scaled_world)

    with django_assert_num_queries(QUERIES_CLOSED):
        policy.can_start(
            sender=scaled_world.learners["in_c1"].user,
            recipient=scaled_world.learners["in_c1_and_c2"].user,
            site=scaled_world.site,
        )


def test_can_start_runs_a_fixed_number_of_queries_for_a_pair_with_no_relationship(
    policy: LayeredMessagingPolicy,
    scaled_world: World,
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    _warm_content_types(scaled_world)

    with django_assert_num_queries(QUERIES_NO_RELATIONSHIP):
        policy.can_start(
            sender=scaled_world.learners["no_cohort"].user,
            recipient=scaled_world.learners["in_c1"].user,
            site=scaled_world.site,
        )
