"""The direct-messaging seeder deletes data: only what belongs to its personas.

qa_helpers is otherwise untested developer tooling. This seeder is the
exception because it deletes a User row to leave a "Deleted user"
conversation behind, and strips the personas' role grants, member rows and
unplanned conversations; a wrong lookup would delete someone else's.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest
from guardian.models import UserObjectPermission
from guardian.shortcuts import assign_perm

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.comms.factories import ConversationFactory
from freedom_ls.comms.models import Conversation, ConversationParticipant, Message
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.learner_management.models import OrganisationMember
from freedom_ls.qa_helpers.management.commands.qa_create_direct_messaging_scenario import (
    DELETED_EMAIL,
    _deleted_partner_conversation,
    _prune_conversations,
    _strip_roles,
)
from freedom_ls.role_based_permissions.factories import ObjectRoleAssignmentFactory
from freedom_ls.role_based_permissions.models import ObjectRoleAssignment

pytestmark = [pytest.mark.fls_internal, pytest.mark.dev_tooling]

NOW = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)


@pytest.mark.django_db
def test_the_deleted_partner_is_the_only_user_removed(mock_site_context) -> None:
    edu = cast(User, UserFactory(email="edu@qa.test", site=mock_site_context))
    bystander = UserFactory(email="bystander@qa.test", site=mock_site_context)

    conversation = _deleted_partner_conversation(
        mock_site_context, {"edu@qa.test": edu}, NOW
    )

    assert not User._base_manager.filter(email=DELETED_EMAIL).exists()
    assert User._base_manager.filter(pk__in=[edu.pk, bystander.pk]).count() == 2
    assert list(
        ConversationParticipant._base_manager.filter(
            conversation=conversation
        ).values_list("user_id", flat=True)
    ) == [edu.pk]
    assert sorted(
        Message._base_manager.filter(conversation=conversation).values_list(
            "sender_id", flat=True
        ),
        key=str,
    ) == sorted([None, edu.pk], key=str)


@pytest.mark.django_db
def test_a_rerun_reuses_the_conversation_and_deletes_nothing(
    mock_site_context,
) -> None:
    edu = cast(User, UserFactory(email="edu@qa.test", site=mock_site_context))
    first = _deleted_partner_conversation(mock_site_context, {"edu@qa.test": edu}, NOW)
    users_before = User._base_manager.count()

    second = _deleted_partner_conversation(mock_site_context, {"edu@qa.test": edu}, NOW)

    assert second.pk == first.pk
    assert Conversation._base_manager.count() == 1
    assert User._base_manager.count() == users_before
    assert second.last_message_at == NOW.replace(day=8)


@pytest.mark.django_db
def test_strip_roles_leaves_other_users_grants(mock_site_context) -> None:
    persona = cast(User, UserFactory(site=mock_site_context))
    bystander = cast(User, UserFactory(site=mock_site_context))
    cohort = CohortFactory()
    for user in (persona, bystander):
        # The role factory also writes the OrganisationMember gate row.
        ObjectRoleAssignmentFactory(user=user, target_object=cohort)

    _strip_roles(mock_site_context, [persona])

    assert list(
        ObjectRoleAssignment._base_manager.values_list("user_id", flat=True)
    ) == [bystander.pk]
    assert list(OrganisationMember._base_manager.values_list("user_id", flat=True)) == [
        bystander.pk
    ]


@pytest.mark.django_db
def test_strip_roles_takes_the_personas_guardian_rows(mock_site_context) -> None:
    # Bulk-deleting role assignments leaves their synced guardian rows behind,
    # still granting view_cohort.
    persona = cast(User, UserFactory(site=mock_site_context))
    bystander = cast(User, UserFactory(site=mock_site_context))
    cohort = CohortFactory()
    for user in (persona, bystander):
        assign_perm("view_cohort", user, cohort)

    _strip_roles(mock_site_context, [persona])

    assert list(UserObjectPermission.objects.values_list("user_id", flat=True)) == [
        bystander.pk
    ]


@pytest.mark.django_db
def test_prune_keeps_planned_and_unrelated_conversations(mock_site_context) -> None:
    persona, other, bystander = (
        cast(User, UserFactory(site=mock_site_context)) for _ in range(3)
    )
    planned = cast(Conversation, ConversationFactory(between=(persona, other)))
    stray = cast(Conversation, ConversationFactory(between=(persona, bystander)))
    unrelated = cast(Conversation, ConversationFactory(between=(other, bystander)))

    _prune_conversations([persona], [planned])

    remaining = set(Conversation._base_manager.values_list("pk", flat=True))
    assert remaining == {planned.pk, unrelated.pk}
    assert stray.pk not in remaining
