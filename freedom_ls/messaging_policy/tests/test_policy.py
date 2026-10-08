"""LayeredMessagingPolicy: the refusals that do not depend on any relationship,
the educator of a learner relationship, the colleague relationship and the
cohort-peer and course-peer candidates resolved through the settings layer."""

from __future__ import annotations

from collections.abc import Iterator
from typing import NamedTuple, cast

import pytest
from pytest_django.fixtures import DjangoAssertNumQueries, SettingsWrapper

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.db.models import Model

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.comms.messaging_policy import MessagingRefusal
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
)
from freedom_ls.learner_management.queries import educators_of
from freedom_ls.learner_management.tests.scenario_world import (
    World,
    build_world,
    custom_role_config,
)
from freedom_ls.messaging_policy.factories import (
    CohortCourseRegistrationMessagingConfigFactory,
    CohortMessagingConfigFactory,
    LearnerCourseRegistrationMessagingConfigFactory,
    LearnerMessagingConfigFactory,
    OrganisationMessagingConfigFactory,
    SiteMessagingConfigFactory,
)
from freedom_ls.messaging_policy.policy import LayeredMessagingPolicy
from freedom_ls.messaging_policy.tests.messaging_world import (
    add_configuration_rows,
    allowed_pairs,
    recipients_pairs,
)
from freedom_ls.role_based_permissions.utils import (
    assign_object_role,
    remove_object_role,
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


QUERIES_RECIPIENTS = 4
QUERIES_ALLOWED = 4
QUERIES_CLOSED = 6
QUERIES_NO_RELATIONSHIP = 6


def open_course_peers(settings: SettingsWrapper) -> None:
    settings.MESSAGING_DEFAULT_FLAGS = {**ALL_CLOSED, "learner_to_course_peer": "open"}


def open_educators(settings: SettingsWrapper, offered: list[str]) -> None:
    settings.MESSAGING_DEFAULT_FLAGS = {**ALL_CLOSED, "learner_to_educator": "open"}
    settings.MESSAGING_OFFERED_EDUCATOR_ROLES = offered


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
        recipient=world.learners["in_o1_and_o2"].user,
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
    add_configuration_rows(world)

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


def _new_organisation() -> Model:
    return cast(Model, CohortFactory().organisation)


def _new_course(organisation: Model) -> Model:
    """A course nobody is registered for, reached through a registration factory so
    no test imports the content app."""
    return cast(
        Model,
        CohortCourseRegistrationFactory(
            cohort=CohortFactory(organisation=organisation), is_active=False
        ).course,
    )


def _register_individually(
    learner: Learner, course: Model
) -> LearnerCourseRegistration | CohortCourseRegistration:
    return cast(
        LearnerCourseRegistration,
        LearnerCourseRegistrationFactory(learner=learner, course=course),
    )


def _register_through_cohort(
    learner: Learner, course: Model
) -> LearnerCourseRegistration | CohortCourseRegistration:
    cohort = CohortFactory(organisation=learner.organisation)
    CohortMembershipFactory(cohort=cohort, learner=learner)
    return cast(
        CohortCourseRegistration,
        CohortCourseRegistrationFactory(cohort=cohort, course=course),
    )


REGISTRATION_PATHS = {
    "individually": _register_individually,
    "through_cohort": _register_through_cohort,
}

REGISTRATION_PATH_PAIRS = [
    ("individually", "individually"),
    ("individually", "through_cohort"),
    ("through_cohort", "individually"),
    ("through_cohort", "through_cohort"),
]


class CoursePeers(NamedTuple):
    sender: Learner
    recipient: Learner
    recipient_registration: LearnerCourseRegistration | CohortCourseRegistration


def _course_peers(
    site: Site, sender_path: str = "individually", recipient_path: str = "individually"
) -> CoursePeers:
    organisation = _new_organisation()
    course = _new_course(organisation)
    sender = LearnerFactory(organisation=organisation)
    recipient = LearnerFactory(organisation=organisation)
    REGISTRATION_PATHS[sender_path](sender, course)
    return CoursePeers(
        sender, recipient, REGISTRATION_PATHS[recipient_path](recipient, course)
    )


def test_a_course_peer_is_closed_by_configuration_out_of_the_box(
    out_of_the_box_policy: LayeredMessagingPolicy, mock_site_context: Site
) -> None:
    peers = _course_peers(mock_site_context)

    decision = out_of_the_box_policy.can_start(
        sender=peers.sender.user, recipient=peers.recipient.user, site=mock_site_context
    )

    assert decision.reason == MessagingRefusal.CLOSED_BY_CONFIGURATION


def test_a_course_peer_is_refused_when_the_flag_is_closed(
    policy: LayeredMessagingPolicy, mock_site_context: Site
) -> None:
    peers = _course_peers(mock_site_context)

    decision = policy.can_start(
        sender=peers.sender.user, recipient=peers.recipient.user, site=mock_site_context
    )

    assert decision.reason == MessagingRefusal.CLOSED_BY_CONFIGURATION


@pytest.mark.parametrize(("sender_path", "recipient_path"), REGISTRATION_PATH_PAIRS)
def test_a_learner_may_start_with_a_course_peer_when_the_flag_is_open(
    policy: LayeredMessagingPolicy,
    mock_site_context: Site,
    settings: SettingsWrapper,
    sender_path: str,
    recipient_path: str,
) -> None:
    open_course_peers(settings)
    peers = _course_peers(mock_site_context, sender_path, recipient_path)

    decision = policy.can_start(
        sender=peers.sender.user, recipient=peers.recipient.user, site=mock_site_context
    )

    assert decision.allowed is True


def test_course_peers_in_different_organisations_have_no_relationship(
    policy: LayeredMessagingPolicy, mock_site_context: Site, settings: SettingsWrapper
) -> None:
    open_course_peers(settings)
    course = _new_course(_new_organisation())
    sender = LearnerFactory(organisation=_new_organisation())
    recipient = LearnerFactory(organisation=_new_organisation())
    _register_individually(sender, course)
    _register_individually(recipient, course)

    decision = policy.can_start(
        sender=sender.user, recipient=recipient.user, site=mock_site_context
    )

    assert decision.reason == MessagingRefusal.NO_RELATIONSHIP


def _remove_recipient_row(peers: CoursePeers) -> None:
    peers.recipient.delete()


def _deactivate_recipient_registration(peers: CoursePeers) -> None:
    peers.recipient_registration.is_active = False
    peers.recipient_registration.save()


CANDIDATE_REMOVALS = {
    "learner_removed": _remove_recipient_row,
    "registration_inactive": _deactivate_recipient_registration,
}


@pytest.mark.parametrize("removal", CANDIDATE_REMOVALS)
@pytest.mark.parametrize("path", REGISTRATION_PATHS)
def test_a_removed_learner_or_inactive_registration_removes_the_candidate(
    policy: LayeredMessagingPolicy,
    mock_site_context: Site,
    settings: SettingsWrapper,
    removal: str,
    path: str,
) -> None:
    open_course_peers(settings)
    peers = _course_peers(mock_site_context, recipient_path=path)
    CANDIDATE_REMOVALS[removal](peers)

    decision = policy.can_start(
        sender=peers.sender.user, recipient=peers.recipient.user, site=mock_site_context
    )

    assert decision.reason == MessagingRefusal.NO_RELATIONSHIP


@pytest.mark.parametrize("removal", CANDIDATE_REMOVALS)
@pytest.mark.parametrize("path", REGISTRATION_PATHS)
def test_a_removed_learner_or_inactive_registration_removes_the_candidate_backwards(
    policy: LayeredMessagingPolicy,
    mock_site_context: Site,
    settings: SettingsWrapper,
    removal: str,
    path: str,
) -> None:
    open_course_peers(settings)
    peers = _course_peers(mock_site_context, recipient_path=path)
    CANDIDATE_REMOVALS[removal](peers)

    decision = policy.can_start(
        sender=peers.recipient.user, recipient=peers.sender.user, site=mock_site_context
    )

    assert decision.reason == MessagingRefusal.NO_RELATIONSHIP


def test_a_learner_starting_with_their_cohort_admin_is_closed_by_configuration_out_of_the_box(
    out_of_the_box_policy: LayeredMessagingPolicy, world: World
) -> None:
    decision = out_of_the_box_policy.can_start(
        sender=world.learners["in_c1"].user,
        recipient=world.role_holders["c1_admin"],
        site=world.site,
    )

    assert decision.reason == MessagingRefusal.CLOSED_BY_CONFIGURATION


@pytest.mark.parametrize(
    ("holder", "reason"),
    [
        ("c1_admin", None),
        ("c1_viewer", MessagingRefusal.CLOSED_BY_CONFIGURATION),
        ("o1_admin", MessagingRefusal.CLOSED_BY_CONFIGURATION),
        ("site_admin", MessagingRefusal.CLOSED_BY_CONFIGURATION),
    ],
)
def test_only_an_offered_educator_role_is_open_when_the_educator_flag_is_open(
    policy: LayeredMessagingPolicy,
    world: World,
    settings: SettingsWrapper,
    holder: str,
    reason: MessagingRefusal | None,
) -> None:
    open_educators(settings, ["cohort_admin"])

    decision = policy.can_start(
        sender=world.learners["in_c1"].user,
        recipient=world.role_holders[holder],
        site=world.site,
    )

    assert decision.reason == reason


def test_a_learner_may_not_start_with_an_offered_educator_when_the_flag_is_closed(
    policy: LayeredMessagingPolicy, world: World, settings: SettingsWrapper
) -> None:
    settings.MESSAGING_OFFERED_EDUCATOR_ROLES = ["cohort_admin"]

    decision = policy.can_start(
        sender=world.learners["in_c1"].user,
        recipient=world.role_holders["c1_admin"],
        site=world.site,
    )

    assert decision.reason == MessagingRefusal.CLOSED_BY_CONFIGURATION


def test_an_opened_learner_reaches_their_organisation_admin_when_that_role_is_offered(
    policy: LayeredMessagingPolicy, mock_site_context: Site, settings: SettingsWrapper
) -> None:
    open_educators(settings, ["organisation_admin"])
    learner = LearnerFactory()
    admin = UserFactory()
    assign_object_role(admin, learner.organisation, "organisation_admin")

    decision = policy.can_start(
        sender=learner.user, recipient=admin, site=mock_site_context
    )

    assert decision.allowed is True


def test_no_educator_is_open_when_no_role_is_offered(
    policy: LayeredMessagingPolicy, world: World, settings: SettingsWrapper
) -> None:
    open_educators(settings, [])

    decisions = {
        policy.can_start(
            sender=world.learners["in_c1"].user,
            recipient=world.role_holders[holder],
            site=world.site,
        ).reason
        for holder in ("c1_admin", "c1_viewer", "o1_admin", "site_admin")
    }

    assert decisions == {MessagingRefusal.CLOSED_BY_CONFIGURATION}


def test_a_role_that_does_not_grant_view_learner_is_never_offered(
    policy: LayeredMessagingPolicy, world: World, settings: SettingsWrapper
) -> None:
    open_educators(settings, ["custom_bystander"])

    decision = policy.can_start(
        sender=world.learners["in_c1"].user,
        recipient=world.role_holders["custom_bystander_o1"],
        site=world.site,
    )

    assert decision.reason == MessagingRefusal.NO_RELATIONSHIP


def test_recipients_for_an_opened_learner_that_are_not_colleagues_are_educators_of_the_row(
    policy: LayeredMessagingPolicy, world: World, settings: SettingsWrapper
) -> None:
    open_educators(settings, ["cohort_admin", "organisation_admin", "site_admin"])
    learner = world.learners["in_c1"]

    recipients = set(policy.recipients_for(sender=learner.user, site=world.site))

    assert recipients <= set(educators_of(learner))


def test_a_learner_reply_to_an_educator_whose_role_was_removed_has_no_relationship(
    policy: LayeredMessagingPolicy, world: World, settings: SettingsWrapper
) -> None:
    open_educators(settings, ["cohort_admin"])
    remove_object_role(
        world.role_holders["c1_admin"], world.cohorts["c1"], "cohort_admin"
    )

    decision = policy.can_reply(
        sender=world.learners["in_c1"].user,
        recipient=world.role_holders["c1_admin"],
        site=world.site,
        conversation=world.learners["in_c1"],
    )

    assert decision.reason == MessagingRefusal.NO_RELATIONSHIP


def test_a_site_row_with_the_cohort_peer_flag_open_beats_a_closed_setting(
    policy: LayeredMessagingPolicy, world: World
) -> None:
    SiteMessagingConfigFactory(site=world.site, learner_to_cohort_peer="open")

    decision = policy.can_start(
        sender=world.learners["in_c1"].user,
        recipient=world.learners["in_c1_and_c2"].user,
        site=world.site,
    )

    assert decision.allowed is True


def test_an_all_inherit_site_row_gives_the_same_outcome_as_no_row(
    policy: LayeredMessagingPolicy, world: World, settings: SettingsWrapper
) -> None:
    open_cohort_peers(settings)
    without_row = allowed_pairs(world, policy)

    SiteMessagingConfigFactory(site=world.site)

    assert allowed_pairs(world, policy) == without_row


def _put_in_cohorts(*cohorts: Cohort, learners: tuple[Learner, ...]) -> None:
    for cohort in cohorts:
        for learner in learners:
            CohortMembershipFactory(cohort=cohort, learner=learner)


def _add_inherit_rows(world: World) -> None:
    for cohort in world.cohorts.values():
        CohortMessagingConfigFactory(cohort=cohort)


def test_one_shared_cohort_opened_on_the_cohort_allows_peers(
    policy: LayeredMessagingPolicy, world: World
) -> None:
    CohortMessagingConfigFactory(
        cohort=world.cohorts["c1"], learner_to_cohort_peer="open"
    )

    decision = policy.can_start(
        sender=world.learners["in_c1"].user,
        recipient=world.learners["in_c1_and_c2"].user,
        site=world.site,
    )

    assert decision.allowed is True


def test_two_shared_cohorts_one_open_one_closed_allows_through_the_open_one(
    policy: LayeredMessagingPolicy, mock_site_context: Site, settings: SettingsWrapper
) -> None:
    open_cohort_peers(settings)
    organisation = _new_organisation()
    sender = LearnerFactory(organisation=organisation)
    recipient = LearnerFactory(organisation=organisation)
    open_cohort = CohortFactory(organisation=organisation)
    closed_cohort = CohortFactory(organisation=organisation)
    CohortMessagingConfigFactory(cohort=open_cohort, learner_to_cohort_peer="open")
    CohortMessagingConfigFactory(cohort=closed_cohort, learner_to_cohort_peer="closed")
    _put_in_cohorts(open_cohort, closed_cohort, learners=(sender, recipient))

    decision = policy.can_start(
        sender=sender.user, recipient=recipient.user, site=mock_site_context
    )

    assert decision.allowed is True


def test_a_closed_organisation_row_closes_a_cohort_left_on_inherit(
    policy: LayeredMessagingPolicy, world: World, settings: SettingsWrapper
) -> None:
    open_cohort_peers(settings)
    OrganisationMessagingConfigFactory(
        organisation=world.organisations["o1"], learner_to_cohort_peer="closed"
    )

    decision = policy.can_start(
        sender=world.learners["in_c1"].user,
        recipient=world.learners["in_c1_and_c2"].user,
        site=world.site,
    )

    assert decision.reason == MessagingRefusal.CLOSED_BY_CONFIGURATION


def test_an_open_organisation_row_opens_a_cohort_left_on_inherit(
    policy: LayeredMessagingPolicy, world: World
) -> None:
    OrganisationMessagingConfigFactory(
        organisation=world.organisations["o1"], learner_to_cohort_peer="open"
    )

    decision = policy.can_start(
        sender=world.learners["in_c1"].user,
        recipient=world.learners["in_c1_and_c2"].user,
        site=world.site,
    )

    assert decision.allowed is True


def test_a_closed_cohort_row_beats_an_open_organisation_row(
    policy: LayeredMessagingPolicy, world: World
) -> None:
    OrganisationMessagingConfigFactory(
        organisation=world.organisations["o1"], learner_to_cohort_peer="open"
    )
    CohortMessagingConfigFactory(
        cohort=world.cohorts["c1"], learner_to_cohort_peer="closed"
    )

    decision = policy.can_start(
        sender=world.learners["in_c1"].user,
        recipient=world.learners["in_c1_and_c2"].user,
        site=world.site,
    )

    assert decision.reason == MessagingRefusal.CLOSED_BY_CONFIGURATION


def test_a_cohort_registration_resolves_through_its_cohort_row(
    policy: LayeredMessagingPolicy, mock_site_context: Site
) -> None:
    peers = _course_peers(mock_site_context, "through_cohort", "individually")
    sender_cohort = Cohort.objects.get(cohortmembership__learner=peers.sender)
    CohortMessagingConfigFactory(cohort=sender_cohort, learner_to_course_peer="open")

    decision = policy.can_start(
        sender=peers.sender.user, recipient=peers.recipient.user, site=mock_site_context
    )

    assert decision.allowed is True


def test_a_closed_organisation_row_closes_a_cohort_registration_left_on_inherit(
    policy: LayeredMessagingPolicy, mock_site_context: Site, settings: SettingsWrapper
) -> None:
    open_course_peers(settings)
    peers = _course_peers(mock_site_context, "through_cohort", "individually")
    OrganisationMessagingConfigFactory(
        organisation=peers.sender.organisation, learner_to_course_peer="closed"
    )

    decision = policy.can_start(
        sender=peers.sender.user, recipient=peers.recipient.user, site=mock_site_context
    )

    assert decision.reason == MessagingRefusal.CLOSED_BY_CONFIGURATION


def test_all_inherit_cohort_rows_give_the_same_outcome_as_no_cohort_rows(
    policy: LayeredMessagingPolicy, world: World, settings: SettingsWrapper
) -> None:
    open_cohort_peers(settings)
    without_rows = allowed_pairs(world, policy)

    _add_inherit_rows(world)

    assert allowed_pairs(world, policy) == without_rows


PEER_FLAGS_CLOSED = {
    "learner_to_cohort_peer": "closed",
    "learner_to_course_peer": "closed",
}


@pytest.mark.parametrize("recipient", ["in_c1_and_c2", "no_cohort"])
def test_a_closed_learner_level_stops_every_peer_candidate(
    policy: LayeredMessagingPolicy,
    world: World,
    settings: SettingsWrapper,
    recipient: str,
) -> None:
    settings.MESSAGING_DEFAULT_FLAGS = {
        **ALL_CLOSED,
        "learner_to_cohort_peer": "open",
        "learner_to_course_peer": "open",
    }
    LearnerMessagingConfigFactory(learner=world.learners["in_c1"], **PEER_FLAGS_CLOSED)

    decision = policy.can_start(
        sender=world.learners["in_c1"].user,
        recipient=world.learners[recipient].user,
        site=world.site,
    )

    assert decision.reason == MessagingRefusal.CLOSED_BY_CONFIGURATION


@pytest.mark.parametrize(
    ("holder", "reason"),
    [("c1_admin", None), ("no_role", MessagingRefusal.NO_RELATIONSHIP)],
)
def test_the_paid_learner_reaches_an_offered_educator_and_not_a_stranger(
    policy: LayeredMessagingPolicy,
    world: World,
    holder: str,
    reason: MessagingRefusal | None,
) -> None:
    LearnerMessagingConfigFactory(
        learner=world.learners["in_c1"], learner_to_educator="open"
    )

    decision = policy.can_start(
        sender=world.learners["in_c1"].user,
        recipient=world.role_holders[holder],
        site=world.site,
    )

    assert decision.reason == reason


def _course_peers_with_individual_sender_open_and_organisation_closed(
    site: Site,
) -> CoursePeers:
    peers = _course_peers(site, "individually", "through_cohort")
    LearnerCourseRegistrationMessagingConfigFactory(
        registration=LearnerCourseRegistration.objects.get(learner=peers.sender),
        learner_to_course_peer="open",
    )
    OrganisationMessagingConfigFactory(
        organisation=peers.sender.organisation, learner_to_course_peer="closed"
    )
    return peers


def test_a_course_opened_on_the_senders_registration_only_allows_the_sender(
    policy: LayeredMessagingPolicy, mock_site_context: Site
) -> None:
    peers = _course_peers_with_individual_sender_open_and_organisation_closed(
        mock_site_context
    )

    decision = policy.can_start(
        sender=peers.sender.user, recipient=peers.recipient.user, site=mock_site_context
    )

    assert decision.allowed is True


def test_a_course_opened_on_the_senders_registration_only_closes_the_recipients_reply(
    policy: LayeredMessagingPolicy, mock_site_context: Site
) -> None:
    peers = _course_peers_with_individual_sender_open_and_organisation_closed(
        mock_site_context
    )

    decision = policy.can_start(
        sender=peers.recipient.user, recipient=peers.sender.user, site=mock_site_context
    )

    assert decision.reason == MessagingRefusal.CLOSED_BY_CONFIGURATION


@pytest.mark.parametrize(
    ("individual", "through_cohort"), [("open", "closed"), ("closed", "open")]
)
def test_individual_and_cohort_registrations_for_one_course_are_separate_candidates(
    policy: LayeredMessagingPolicy,
    mock_site_context: Site,
    individual: str,
    through_cohort: str,
) -> None:
    organisation = _new_organisation()
    course = _new_course(organisation)
    sender = LearnerFactory(organisation=organisation)
    recipient = LearnerFactory(organisation=organisation)
    individual_registration = _register_individually(sender, course)
    cohort_registration = _register_through_cohort(sender, course)
    _register_individually(recipient, course)
    LearnerCourseRegistrationMessagingConfigFactory(
        registration=individual_registration, learner_to_course_peer=individual
    )
    CohortCourseRegistrationMessagingConfigFactory(
        registration=cohort_registration, learner_to_course_peer=through_cohort
    )

    decision = policy.can_start(
        sender=sender.user, recipient=recipient.user, site=mock_site_context
    )

    assert decision.allowed is True


def test_an_educator_with_roles_in_two_organisations_is_reached_through_the_open_one(
    policy: LayeredMessagingPolicy, mock_site_context: Site, settings: SettingsWrapper
) -> None:
    settings.MESSAGING_OFFERED_EDUCATOR_ROLES = ["organisation_admin"]
    closed_organisation = _new_organisation()
    open_organisation = _new_organisation()
    shared_user = UserFactory()
    LearnerFactory(user=shared_user, organisation=closed_organisation)
    LearnerFactory(user=shared_user, organisation=open_organisation)
    educator = UserFactory()
    assign_object_role(educator, closed_organisation, "organisation_admin")
    assign_object_role(educator, open_organisation, "organisation_admin")
    OrganisationMessagingConfigFactory(
        organisation=closed_organisation, learner_to_educator="closed"
    )
    OrganisationMessagingConfigFactory(
        organisation=open_organisation, learner_to_educator="open"
    )

    decision = policy.can_start(
        sender=shared_user, recipient=educator, site=mock_site_context
    )

    assert decision.allowed is True


@pytest.mark.parametrize(
    ("sender", "recipient"),
    [("in_c1", "in_c1_and_c2"), ("in_c1_and_c2", "in_c1")],
)
def test_closing_peer_configuration_on_both_learner_rows_refuses_the_reply(
    policy: LayeredMessagingPolicy,
    world: World,
    settings: SettingsWrapper,
    sender: str,
    recipient: str,
) -> None:
    settings.MESSAGING_DEFAULT_FLAGS = {
        **ALL_CLOSED,
        "learner_to_cohort_peer": "open",
        "learner_to_course_peer": "open",
    }
    LearnerMessagingConfigFactory(learner=world.learners["in_c1"], **PEER_FLAGS_CLOSED)
    LearnerMessagingConfigFactory(
        learner=world.learners["in_c1_and_c2"], **PEER_FLAGS_CLOSED
    )

    decision = policy.can_reply(
        sender=world.learners[sender].user,
        recipient=world.learners[recipient].user,
        site=world.site,
        conversation=world.learners[sender],
    )

    assert decision.reason == MessagingRefusal.CLOSED_BY_CONFIGURATION


def test_a_site_row_offering_organisation_admin_lets_an_opened_learner_reach_their_organisation_admin(
    policy: LayeredMessagingPolicy, world: World
) -> None:
    SiteMessagingConfigFactory(
        site=world.site,
        learner_to_educator="open",
        offered_educator_roles=["organisation_admin"],
    )

    decision = policy.can_start(
        sender=world.learners["in_c1"].user,
        recipient=world.role_holders["o1_admin"],
        site=world.site,
    )

    assert decision.allowed is True


def test_a_site_row_offering_organisation_admin_replaces_the_offered_cohort_admin(
    policy: LayeredMessagingPolicy, world: World
) -> None:
    SiteMessagingConfigFactory(
        site=world.site,
        learner_to_educator="open",
        offered_educator_roles=["organisation_admin"],
    )

    decision = policy.can_start(
        sender=world.learners["in_c1"].user,
        recipient=world.role_holders["c1_admin"],
        site=world.site,
    )

    assert decision.reason == MessagingRefusal.CLOSED_BY_CONFIGURATION


def test_a_site_row_offering_no_roles_offers_nobody(
    policy: LayeredMessagingPolicy, world: World
) -> None:
    SiteMessagingConfigFactory(
        site=world.site, learner_to_educator="open", offered_educator_roles=[]
    )

    decision = policy.can_start(
        sender=world.learners["in_c1"].user,
        recipient=world.role_holders["c1_admin"],
        site=world.site,
    )

    assert decision.reason == MessagingRefusal.CLOSED_BY_CONFIGURATION


def test_a_site_row_with_no_offered_roles_value_uses_the_setting(
    policy: LayeredMessagingPolicy, world: World
) -> None:
    SiteMessagingConfigFactory(
        site=world.site, learner_to_educator="open", offered_educator_roles=None
    )

    decision = policy.can_start(
        sender=world.learners["in_c1"].user,
        recipient=world.role_holders["c1_admin"],
        site=world.site,
    )

    assert decision.allowed is True


def test_a_stored_offered_role_unknown_to_the_site_is_ignored(
    policy: LayeredMessagingPolicy, world: World
) -> None:
    SiteMessagingConfigFactory(
        site=world.site,
        learner_to_educator="open",
        offered_educator_roles=["no_such_role"],
    )

    decision = policy.can_start(
        sender=world.learners["in_c1"].user,
        recipient=world.role_holders["c1_admin"],
        site=world.site,
    )

    assert decision.reason == MessagingRefusal.CLOSED_BY_CONFIGURATION
