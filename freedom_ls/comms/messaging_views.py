"""Direct-message views: the thread page and sending into it."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

from django.contrib.sites.models import Site
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from freedom_ls.accounts.models import User
from freedom_ls.comms.config import config
from freedom_ls.comms.messaging import (
    SendResult,
    closed_note_copy,
    decode_cursor,
    encode_cursor,
    entry_for_message,
    inbox_for,
    latest_page,
    mark_conversation_read,
    other_participant,
    page_before,
    refusal_alert_copy,
    render_message_entries,
    reply_decision,
    search_recipients,
    send_message,
    unread_conversation_count,
)
from freedom_ls.comms.messaging_loader import get_messaging_policy
from freedom_ls.comms.messaging_policy import MessagingRefusal
from freedom_ls.comms.models import Conversation, Message
from freedom_ls.comms.views import messaging_view
from freedom_ls.site_aware_models.models import get_cached_site

if TYPE_CHECKING:
    from django.db.models import QuerySet


def participant_conversation(request: HttpRequest, pk: UUID) -> Conversation:
    """The conversation ``pk`` if the signed-in user takes part in it, else 404.

    The site-aware manager hides another site's conversations, so a pk from
    another site is a 404 as well.
    """
    return cast(
        "Conversation", get_object_or_404(inbox_for(cast("User", request.user)), pk=pk)
    )


@dataclass(frozen=True, slots=True)
class InboxRow:
    conversation: Conversation
    other: User | None
    can_reply: bool


def inbox_rows(user: User) -> list[InboxRow]:
    rows: list[InboxRow] = []
    for conversation in inbox_for(user):
        decision = reply_decision(viewer=user, conversation=conversation)
        rows.append(
            InboxRow(
                conversation, other_participant(conversation, user), decision.allowed
            )
        )
    return rows


def _inbox_context(
    request: HttpRequest, current: Conversation | None = None
) -> dict[str, object]:
    return {
        "inbox_rows": inbox_rows(cast("User", request.user)),
        "current_pk": current.pk if current is not None else None,
    }


def _composer_context(
    *,
    client_key: UUID,
    draft: str = "",
    alert: str = "",
    conversation: Conversation | None = None,
    recipient: User | None = None,
) -> dict[str, object]:
    """What the composer partial needs.

    A composer for an existing conversation posts to its ``send`` URL and
    appends the new message to the log. A composer for a first message posts to
    ``start`` with the recipient, and replaces itself when refused.
    """
    if conversation is not None:
        action_url = reverse("conversations:send", kwargs={"pk": conversation.pk})
    else:
        action_url = reverse("conversations:start")
    return {
        "client_key": client_key,
        "draft": draft,
        "alert": alert,
        "max_length": config.MESSAGE_MAX_LENGTH,
        "action_url": action_url,
        "recipient": recipient,
    }


def thread_context(
    request: HttpRequest, conversation: Conversation
) -> dict[str, object]:
    viewer = cast("User", request.user)
    other = other_participant(conversation, viewer)
    decision = reply_decision(viewer=viewer, conversation=conversation)
    shown, has_older = latest_page(conversation)
    closed_heading, closed_body = ("", "")
    if not decision.allowed:
        closed_heading, closed_body = closed_note_copy(decision.reason, other)
    return {
        "conversation": conversation,
        "other": other,
        "decision": decision,
        "closed_heading": closed_heading,
        "closed_body": closed_body,
        "thread_messages": shown,
        "thread_entries": render_message_entries(shown, None),
        "older_cursor": encode_cursor(shown[0]) if has_older and shown else "",
        "composer": _composer_context(client_key=uuid4(), conversation=conversation),
        "page_size": config.MESSAGE_PAGE_SIZE,
        "back_url": reverse("conversations:inbox"),
    }


@messaging_view
def thread(request: HttpRequest, pk: UUID) -> HttpResponse:
    conversation = participant_conversation(request, pk)
    context = thread_context(request, conversation)
    shown = cast("list[Message]", context["thread_messages"])
    if shown:
        # Marked up to the newest message on the page, not to now, so a message
        # that lands between this render and the mark stays unread.
        mark_conversation_read(
            user=cast("User", request.user),
            conversation=conversation,
            up_to=shown[-1].created_at,
        )
    context.update(_inbox_context(request, conversation))
    return render(request, "comms/thread.html", context)


@messaging_view
def inbox(request: HttpRequest) -> HttpResponse:
    """The conversation list. A history-restore request needs the full page."""
    is_fragment = (
        request.headers.get("HX-Request") == "true"
        and request.headers.get("HX-History-Restore-Request") != "true"
    )
    template_name = (
        "comms/partials/conversation_list.html#conversation-list"
        if is_fragment
        else "comms/inbox.html"
    )
    viewer = cast("User", request.user)
    site = cast("Site", get_cached_site(request))
    context = _inbox_context(request)
    context["has_recipients"] = (
        get_messaging_policy().recipients_for(sender=viewer, site=site).exists()
    )
    return render(request, template_name, context)


def _send_response(
    request: HttpRequest,
    result: SendResult,
    conversation: Conversation | None,
    draft: str,
    client_key: UUID,
    recipient: User | None = None,
) -> HttpResponse:
    """The answer to a send, shared by every view that posts a message.

    A stored message in an existing thread answers with its log entry plus a
    fresh composer swapped in out of band. A first message (``recipient`` set)
    answers by loading the new thread. A refusal or body error answers 422 with
    the composer holding the draft, the same key and the reason; the retarget
    headers point the global 422 swap at the composer instead of the log.
    """
    viewer = cast("User", request.user)
    is_htmx = request.headers.get("HX-Request") == "true"
    if result.message is not None:
        sent_to = cast("Conversation", result.conversation)
        thread_url = reverse("conversations:thread", kwargs={"pk": sent_to.pk})
        if not is_htmx:
            return redirect(thread_url)
        if recipient is not None:
            response = HttpResponse(status=204)
            response["HX-Location"] = json.dumps({"path": thread_url})
            return response
        body = render_to_string(
            "comms/partials/message_entry.html",
            {"entry": entry_for_message(result.message), "conversation": sent_to},
            request,
        )
        body += render_to_string(
            "comms/partials/composer.html",
            {
                "conversation": sent_to,
                "other": other_participant(sent_to, viewer),
                "composer": _composer_context(client_key=uuid4(), conversation=sent_to),
                "oob": True,
            },
            request,
        )
        return HttpResponse(body)

    other = (
        recipient if conversation is None else other_participant(conversation, viewer)
    )
    alert = result.body_error or refusal_alert_copy(result.refusal, other)
    context = {
        "conversation": conversation,
        "other": other,
        "recipient": recipient,
        "composer": _composer_context(
            client_key=client_key,
            draft=draft,
            alert=alert,
            conversation=conversation,
            recipient=recipient,
        ),
    }
    if not is_htmx:
        if conversation is None:
            return render(request, "comms/start.html", context, status=422)
        return render(
            request,
            "comms/thread.html",
            {
                **thread_context(request, conversation),
                **_inbox_context(request, conversation),
                **context,
            },
            status=422,
        )
    response = HttpResponse(
        render_to_string("comms/partials/composer.html", context, request),
        status=422,
    )
    response["HX-Retarget"] = "#composer"
    response["HX-Reswap"] = "outerHTML"
    return response


@messaging_view
@require_POST
def send(request: HttpRequest, pk: UUID) -> HttpResponse:
    conversation = participant_conversation(request, pk)
    try:
        client_key = UUID(request.POST.get("client_key", ""))
    except ValueError:
        return HttpResponseBadRequest("client_key must be a UUID")
    draft = request.POST.get("body", "")
    site = cast("Site", get_cached_site(request))
    result = send_message(
        sender=cast("User", request.user),
        body=draft,
        client_key=client_key,
        site=site,
        conversation=conversation,
    )
    return _send_response(request, result, conversation, draft, client_key)


def _user_pk(raw: str | None) -> int:
    try:
        return int(raw or "")
    except ValueError:
        raise Http404("recipient must be a user id") from None


def _offered_recipients(request: HttpRequest) -> QuerySet[User]:
    site = cast("Site", get_cached_site(request))
    return get_messaging_policy().recipients_for(
        sender=cast("User", request.user), site=site
    )


def _picker_context(request: HttpRequest, term: str) -> dict[str, object]:
    """What the picker partial needs: the search outcome and the URLs it links to."""
    site = cast("Site", get_cached_site(request))
    return {
        "search": search_recipients(
            sender=cast("User", request.user),
            site=site,
            term=term,
            include_email=False,
        ),
        "term": term.strip(),
        "include_email": False,
        "search_url": reverse("conversations:recipient_search"),
        "choose_url": reverse("conversations:start"),
    }


def _start_get(request: HttpRequest) -> HttpResponse:
    raw = request.GET.get("recipient")
    if raw is None:
        return render(
            request,
            "comms/start.html",
            {"recipient": None, **_picker_context(request, request.GET.get("q", ""))},
        )
    recipient = get_object_or_404(_offered_recipients(request), pk=_user_pk(raw))
    return render(
        request,
        "comms/start.html",
        {
            "recipient": recipient,
            "other": recipient,
            "composer": _composer_context(client_key=uuid4(), recipient=recipient),
        },
    )


def _start_post(request: HttpRequest) -> HttpResponse:
    try:
        client_key = UUID(request.POST.get("client_key", ""))
    except ValueError:
        return HttpResponseBadRequest("client_key must be a UUID")
    draft = request.POST.get("body", "")
    site = cast("Site", get_cached_site(request))
    recipient = get_object_or_404(User, pk=_user_pk(request.POST.get("recipient")))
    if not _offered_recipients(request).filter(pk=recipient.pk).exists():
        # Not someone the policy offers this sender: refused the way a policy
        # refusal is, with the draft kept and nothing stored.
        result = SendResult(refusal=MessagingRefusal.NO_RELATIONSHIP)
    else:
        result = send_message(
            sender=cast("User", request.user),
            body=draft,
            client_key=client_key,
            site=site,
            recipient=recipient,
        )
    return _send_response(request, result, None, draft, client_key, recipient=recipient)


@messaging_view
@require_http_methods(["GET", "POST"])
def start(request: HttpRequest) -> HttpResponse:
    """The new-message page: a known recipient's composer, or the picker region."""
    if request.method == "POST":
        return _start_post(request)
    return _start_get(request)


@messaging_view
def partial_unread_badge(request: HttpRequest) -> HttpResponse:
    """The header Messages badge content: the sr-only label and the count."""
    return render(
        request,
        "comms/partials/unread_badge.html",
        {"unread_count": unread_conversation_count(cast("User", request.user))},
    )


@messaging_view
def partial_recipient_search(request: HttpRequest) -> HttpResponse:
    """The picker's result list for the typed term, without a page around it."""
    return render(
        request,
        "comms/partials/recipient_picker.html#results",
        _picker_context(request, request.GET.get("q", "")),
    )


@messaging_view
def partial_thread_older(request: HttpRequest, pk: UUID) -> HttpResponse:
    """The page of messages older than ``?before=``, for prepending to the log.

    The first message already on screen is re-rendered out of band, because
    its day separator and sender line depend on what now sits above it. The
    load-earlier control is replaced out of band with the next cursor, or with
    nothing once no older message exists.
    """
    conversation = participant_conversation(request, pk)
    cursor = decode_cursor(request.GET.get("before", ""))
    if cursor is None:
        return HttpResponseBadRequest("before must be a cursor")
    older, has_more = page_before(conversation, cursor)
    boundary = Message.objects.filter(
        conversation=conversation, pk=cursor[1], created_at=cursor[0]
    ).select_related("sender")
    body = ""
    for entry in render_message_entries(older, None):
        body += render_to_string(
            "comms/partials/message_entry.html", {"entry": entry}, request
        )
    boundary_message = boundary.first()
    if older and boundary_message is not None:
        body += render_to_string(
            "comms/partials/message_entry.html",
            {
                "entry": render_message_entries([boundary_message], older[-1])[0],
                "oob": True,
            },
            request,
        )
    body += render_to_string(
        "comms/partials/thread_older.html",
        {
            "conversation": conversation,
            "older_cursor": encode_cursor(older[0]) if has_more and older else "",
            "oob": True,
        },
        request,
    )
    return HttpResponse(body)
