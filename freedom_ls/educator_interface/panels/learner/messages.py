"""The learner page's Messages tab: the educator's conversation, the oversight list and their actions."""

from __future__ import annotations

from functools import cached_property
from typing import cast
from uuid import UUID, uuid4

from django.contrib.sites.models import Site
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from freedom_ls.accounts.models import User
from freedom_ls.audit_log.writer import record_entry
from freedom_ls.comms.config import config as comms_config
from freedom_ls.comms.messaging import (
    other_participant,
    refusal_alert_copy,
    send_message,
)
from freedom_ls.comms.messaging_views import (
    CONVERSATION_CHANGED,
    composer_context,
    posted_client_key,
    read_only_thread_context,
    thread_context,
)
from freedom_ls.educator_interface.messaging import (
    OwnConversation,
    other_educator_conversations,
    own_conversation_with,
)
from freedom_ls.educator_interface.panels.common.ids import uuid_or_404
from freedom_ls.learner_management.models import Learner
from freedom_ls.learner_management.queries import (
    VIEW_CONVERSATION,
    site_level_admins,
)
from freedom_ls.panel_framework.actions import PanelAction
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.panels import Panel, PanelStack
from freedom_ls.site_aware_models.models import get_cached_site

__all__ = [
    "LearnerMessagesPanel",
    "LearnerMessagesStack",
    "LearnerOtherConversationsPanel",
    "SendToLearnerAction",
    "ViewConversationAction",
    "_oversight_role_label",
]


class LearnerMessagesPanel(Panel):
    """The educator's own conversation with the learner. The thread pane runs
    edge to edge, so the card is flush.

    It declares no refresh events: a re-fetch would mark the thread read again
    for nothing, and the thread polls for new messages itself.
    """

    model = Learner
    title = "Messages"
    template_name = "educator_interface/panels/learner_messages.html"
    card_flush = True

    def has_permission(self, request: HttpRequest) -> bool:
        return comms_config.MESSAGING_ENABLED and super().has_permission(request)

    @cached_property
    def _own(self) -> OwnConversation:
        return own_conversation_with(self.request, cast(Learner, self.instance))

    def get_actions(self) -> list[PanelAction]:
        return [SendToLearnerAction()]

    def get_context_data(
        self,
        *,
        own: OwnConversation | None = None,
        draft: str = "",
        client_key: UUID | None = None,
        alert: str = "",
    ) -> dict[str, object]:
        """The tab's context. ``own`` is the educator's side when the caller
        has already looked it up. The other keyword arguments re-render the
        tab after a refused send with the educator's draft and the refusal,
        which shows even when the policy no longer lets them write."""
        context = super().get_context_data()
        learner = cast(Learner, self.instance)
        if own is None:
            own = self._own
        may_write = own.allowed or bool(alert)
        context["learner"] = learner
        if own.conversation is not None:
            context.update(thread_context(self.request, own.conversation))
            context.pop("back_url")
        else:
            context["other"] = learner.user
        if may_write:
            context["composer"] = composer_context(
                client_key=client_key or uuid4(),
                draft=draft,
                alert=alert,
                conversation=own.conversation,
                recipient=None if own.conversation is not None else learner.user,
                action_url=SendToLearnerAction().get_action_url(self.ctx),
                swap_target=self.region_id,
            )
        return context


class LearnerOtherConversationsPanel(Panel):
    """The learner's conversations with their other educators, for someone
    with oversight of the learner: one row each, opening the conversation
    read-only in the app modal."""

    model = Learner
    title = "Other educator conversations"
    template_name = "educator_interface/panels/learner_other_conversations.html"

    def has_permission(self, request: HttpRequest) -> bool:
        return (
            comms_config.MESSAGING_ENABLED
            and super().has_permission(request)
            and bool(self.available_actions)
        )

    def get_actions(self) -> list[PanelAction]:
        return [ViewConversationAction()]

    def get_context_data(self) -> dict[str, object]:
        context = super().get_context_data()
        learner = cast(Learner, self.instance)
        rows = other_educator_conversations(cast(User, self.request.user), learner)
        context["oversight_rows"] = [
            (c, other_participant(c, learner.user)) for c in rows
        ]
        return context


class LearnerMessagesStack(PanelStack):
    """The learner's Messages tab: the educator's own conversation, then the
    learner's other educator conversations, each its own panel."""

    model = Learner
    title = "Messages"
    children = {
        "conversation": LearnerMessagesPanel,
        "others": LearnerOtherConversationsPanel,
    }


class SendToLearnerAction(PanelAction):
    """The Messages tab's composer posts here, so the answer is the tab itself
    re-rendered, never a redirect to the messages page."""

    action_name = "send"
    renders_in_footer = False

    def has_permission(self, ctx: PanelContext) -> bool:
        return comms_config.MESSAGING_ENABLED and super().has_permission(ctx)

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        request = ctx.request
        learner = cast(Learner, ctx.instance)
        own = own_conversation_with(request, learner)
        client_key = posted_client_key(request)
        draft = request.POST.get("body", "")
        result = send_message(
            sender=cast(User, request.user),
            body=draft,
            client_key=client_key,
            site=cast(Site, get_cached_site(request)),
            conversation=own.conversation,
            recipient=None if own.conversation is not None else learner.user,
        )
        panel = LearnerMessagesPanel(ctx)
        if result.message is not None:
            # A first send created the conversation, so look it up afresh.
            response = render(
                request,
                panel.template_name,
                panel.get_context_data(
                    own=own if own.conversation is not None else None
                ),
            )
            response["HX-Trigger"] = CONVERSATION_CHANGED
            return response
        alert = result.body_error or refusal_alert_copy(result.refusal, learner.user)
        return render(
            request,
            panel.template_name,
            panel.get_context_data(
                own=own, draft=draft, client_key=client_key, alert=alert
            ),
            status=422,
        )


class ViewConversationAction(PanelAction):
    """Opens one of the learner's educator conversations read-only in the app
    modal, for someone who holds oversight of the learner. Every open is
    recorded in the learner's history, so only the page's own htmx request
    may open one: a plain GET from a prefetch or a cross-site tag must not
    leave a false entry."""

    action_name = "view_conversation"
    capability = VIEW_CONVERSATION
    renders_in_footer = False
    template_name = "educator_interface/modal/conversation_oversight.html"

    def has_permission(self, ctx: PanelContext) -> bool:
        return comms_config.MESSAGING_ENABLED and super().has_permission(ctx)

    def get_context_data(self, ctx: PanelContext) -> dict[str, object]:
        request = ctx.request
        if request.headers.get("HX-Request") != "true":
            raise Http404
        learner = cast(Learner, ctx.instance)
        viewer = cast(User, request.user)
        conversation = get_object_or_404(
            other_educator_conversations(viewer, learner),
            pk=uuid_or_404(request.GET.get("conversation")),
        )
        educator = other_participant(conversation, learner.user)
        record_entry(
            action="conversation.viewed",
            actor=viewer,
            target=conversation,
            target_label=(
                f"Conversation with {educator.display_name if educator else 'Deleted user'}"
            ),
            organisation=learner.organisation,
            subjects=[learner],
        )
        return {
            **read_only_thread_context(
                conversation,
                other=educator,
                older_url=reverse(
                    "educator_interface:oversight_thread_older",
                    kwargs={
                        "organisation_slug": learner.organisation.slug,
                        "learner_pk": str(learner.pk),
                        "conversation_pk": str(conversation.pk),
                    },
                ),
            ),
            "viewer_role_label": _oversight_role_label(viewer, learner),
        }

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        # Opening is a read; there is nothing to submit.
        raise Http404


def _oversight_role_label(viewer: User, learner: Learner) -> str:
    """How the read-only banner names the viewer's access: a site admin reads
    through the site grant, anyone else holding the permission is an
    organisation admin of the learner's organisation."""
    if site_level_admins(learner.site).filter(pk=viewer.pk).exists():
        return "a site admin"
    return "an organisation admin"
