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
    return {
        (sender_name, recipient_name)
        for sender_name, sender in users.items()
        for recipient_name, recipient in users.items()
        if policy.recipients_for(sender=sender, site=world.site)
        .filter(pk=recipient.pk)
        .exists()
    }


def allowed_pairs(world: World, policy: LayeredMessagingPolicy) -> set[tuple[str, str]]:
    """(sender, recipient) for every pair can_start allows."""
    users = world_users(world)
    return {
        (sender_name, recipient_name)
        for sender_name, sender in users.items()
        for recipient_name, recipient in users.items()
        if policy.can_start(sender=sender, recipient=recipient, site=world.site).allowed
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
