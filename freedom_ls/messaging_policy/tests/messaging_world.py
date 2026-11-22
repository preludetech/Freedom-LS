"""Set helpers that compare the two questions a messaging policy answers over
every user in a scenario world."""

from __future__ import annotations

from freedom_ls.accounts.models import User
from freedom_ls.learner_management.models import (
    CohortCourseRegistration,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.tests.scenario_world import World
from freedom_ls.messaging_policy.factories import (
    CohortCourseRegistrationMessagingConfigFactory,
    CohortMessagingConfigFactory,
    LearnerCourseRegistrationMessagingConfigFactory,
    LearnerMessagingConfigFactory,
    OrganisationMessagingConfigFactory,
)
from freedom_ls.messaging_policy.policy import LayeredMessagingPolicy


def world_users(world: World) -> dict[str, User]:
    """Every user in the world by name: role holders, then learners' users."""
    return {
        **world.role_holders,
        **{name: learner.user for name, learner in world.learners.items()},
    }


def recipients_pairs(
    world: World, policy: LayeredMessagingPolicy
) -> set[tuple[str, str]]:
    """(sender, recipient) for every recipient in recipients_for(sender)."""
    users = world_users(world)
    reached_by: dict[int, set[int]] = {}
    for sender in users.values():
        reached_by[sender.pk] = set(
            policy.recipients_for(sender=sender, site=world.site).values_list(
                "pk", flat=True
            )
        )
    return {
        (sender_name, recipient_name)
        for sender_name, sender in users.items()
        for recipient_name, recipient in users.items()
        if recipient.pk in reached_by[sender.pk]
    }


def learner_senders(world: World) -> dict[str, User]:
    """The senders a candidate row can change the outcome for: every learner's
    user, plus one role holder who holds no learner row. A user with no learner
    row has no candidates, so only the role route decides who it may start with
    and no configuration row is read."""
    return {
        **{name: learner.user for name, learner in world.learners.items()},
        "c1_admin": world.role_holders["c1_admin"],
    }


def allowed_pairs(
    world: World,
    policy: LayeredMessagingPolicy,
    senders: dict[str, User] | None = None,
) -> set[tuple[str, str]]:
    """(sender, recipient) for every pair can_start allows, over `senders`
    (every user in the world when omitted). Two names for one user share an
    answer, so the policy is asked once per pair of users."""
    users = world_users(world)
    answers: dict[tuple[int, int], bool] = {}
    for sender in (senders or users).values():
        for recipient in users.values():
            if (sender.pk, recipient.pk) not in answers:
                answers[(sender.pk, recipient.pk)] = policy.can_start(
                    sender=sender, recipient=recipient, site=world.site
                ).allowed
    return {
        (sender_name, recipient_name)
        for sender_name, sender in (senders or users).items()
        for recipient_name, recipient in users.items()
        if answers[(sender.pk, recipient.pk)]
    }


def add_configuration_rows(world: World) -> None:
    """One configuration row per level below the site: an open cohort, a closed
    organisation, an open learner row, an open individual registration and a
    closed cohort registration."""
    every_flag_open = {
        "learner_to_educator": "open",
        "learner_to_cohort_peer": "open",
        "learner_to_course_peer": "open",
    }
    CohortMessagingConfigFactory(cohort=world.cohorts["c1"], **every_flag_open)
    OrganisationMessagingConfigFactory(
        organisation=world.organisations["o2"],
        learner_to_educator="closed",
        learner_to_cohort_peer="closed",
        learner_to_course_peer="closed",
    )
    LearnerMessagingConfigFactory(
        learner=world.learners["in_c1_and_c2"], **every_flag_open
    )
    LearnerCourseRegistrationMessagingConfigFactory(
        registration=LearnerCourseRegistration.objects.get(
            learner=world.learners["no_cohort"]
        ),
        learner_to_course_peer="open",
    )
    CohortCourseRegistrationMessagingConfigFactory(
        registration=CohortCourseRegistration.objects.get(cohort=world.cohorts["c1"]),
        learner_to_course_peer="closed",
    )
