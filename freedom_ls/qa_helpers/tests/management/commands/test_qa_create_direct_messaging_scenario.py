"""The direct-messaging seeder deletes a user: only the partner it made itself.

qa_helpers is otherwise untested developer tooling. This seeder is the
exception because it deletes a User row to leave a "Deleted user"
conversation behind, and a wrong lookup would delete a real persona.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.comms.models import Conversation, ConversationParticipant, Message
from freedom_ls.qa_helpers.management.commands.qa_create_direct_messaging_scenario import (
    DELETED_EMAIL,
    _deleted_partner_conversation,
)

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
