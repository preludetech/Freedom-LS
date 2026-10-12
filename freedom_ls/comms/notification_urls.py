"""URL builders for notification categories that target comms objects."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import reverse

if TYPE_CHECKING:
    from freedom_ls.comms.models import Conversation


def conversation_url(conversation: Conversation) -> str:
    return reverse("conversations:thread", kwargs={"pk": conversation.pk})
