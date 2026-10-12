"""conversation_url reverses the thread route for a conversation."""

from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.comms.factories import ConversationFactory
from freedom_ls.comms.notification_urls import conversation_url


@pytest.mark.django_db
def test_conversation_url_is_the_thread_page(mock_site_context) -> None:
    conversation = ConversationFactory(between=(UserFactory(), UserFactory()))

    assert conversation_url(conversation) == reverse(
        "conversations:thread", kwargs={"pk": conversation.pk}
    )
