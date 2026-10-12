"""Direct-message views: the thread page and sending into it."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
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
    messages_after,
    new_messages_announcement,
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


CONVERSATION_CHANGED = json.dumps({"conversationChanged": {}})


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
    rows = inbox_rows(cast("User", request.user))
    stamps = [
        row.conversation.last_message_at
        for row in rows
        if row.conversation.last_message_at is not None
    ]
    return {
        "inbox_rows": rows,
        "inbox_since": max(stamps).isoformat() if stamps else "",
        "inbox_poll_seconds": config.MESSAGE_INBOX_POLL_SECONDS,
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
        "thread_cursor": encode_cursor(shown[-1]) if shown else "",
        "thread_poll_seconds": config.MESSAGE_THREAD_POLL_SECONDS,
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
    context = _inbox_context(request)
    context["has_recipients"] = _has_recipients(request)
    return render(request, template_name, context)


def _has_recipients(request: HttpRequest) -> bool:
    viewer = cast("User", request.user)
    site = cast("Site", get_cached_site(request))
    return get_messaging_policy().recipients_for(sender=viewer, site=site).exists()


@messaging_view
def partial_inbox_poll(request: HttpRequest) -> HttpResponse:
    """The refreshed conversation list, or 204 when nothing is newer.

    The page sends the newest ``last_message_at`` its list shows (``since``) and
    the pk of the open thread (``current``), which keeps ``aria-current`` on
    that row. A missing or malformed ``since`` re-renders the list.
    """
    viewer = cast("User", request.user)
    try:
        since = datetime.fromisoformat(request.GET.get("since", ""))
    except ValueError:
        since = None
    if (
        since is not None
        and since.tzinfo is not None
        and not inbox_for(viewer).filter(last_message_at__gt=since).exists()
    ):
        return HttpResponse(status=204)

    try:
        current_pk = UUID(request.GET.get("current", ""))
    except ValueError:
        current_pk = None
    current = (
        inbox_for(viewer).filter(pk=current_pk).first()
        if current_pk is not None
        else None
    )
    context = _inbox_context(request, current)
    context["has_recipients"] = _has_recipients(request)
    body = render_to_string(
        "comms/partials/conversation_list.html#conversation-list", context, request
    )
    body += render_to_string(
        "comms/partials/inbox_since.html", {**context, "oob": True}, request
    )
    return HttpResponse(body)


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
            "comms/partials/thread_cursor.html",
            {"thread_cursor": encode_cursor(result.message), "oob": True},
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
        response = HttpResponse(body)
        response["HX-Trigger"] = CONVERSATION_CHANGED
        return response

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


def _boundary_message(
    conversation: Conversation, cursor: tuple[datetime, UUID] | None
) -> Message | None:
    """The message a cursor names, which new entries are laid out against."""
    if cursor is None:
        return None
    return cast(
        "Message | None",
        Message.objects.filter(
            conversation=conversation, pk=cursor[1], created_at=cursor[0]
        )
        .select_related("sender")
        .first(),
    )


def _incoming_announcement(incoming: list[Message]) -> str:
    sender = incoming[-1].sender
    name = sender.display_name if sender is not None else "Deleted user"
    return new_messages_announcement(len(incoming), name)


@messaging_view
def partial_thread_poll(request: HttpRequest, pk: UUID) -> HttpResponse:
    """What changed in the thread since the page's cursor, or 204 for nothing.

    The page sends its newest cursor, whether its composer is the form
    (``composer=open``) or the closed note, and whether the form holds typed
    text (``draft=1``). New messages answer as entries to append, with the
    cursor out of band. Incoming ones mark the thread read and carry the
    screen-reader announcement. When the policy's decision no longer matches
    the composer on screen, the other one is swapped in, unless a draft sits in
    the form: replacing it would throw the text away.
    """
    conversation = participant_conversation(request, pk)
    raw_cursor = request.GET.get("after", "")
    cursor = decode_cursor(raw_cursor)
    if raw_cursor and cursor is None:
        return HttpResponseBadRequest("after must be a cursor")
    viewer = cast("User", request.user)
    other = other_participant(conversation, viewer)
    new = messages_after(conversation, cursor)
    decision = reply_decision(viewer=viewer, conversation=conversation)
    flipped = decision.allowed != (request.GET.get("composer") == "open")
    if not new and not flipped:
        return HttpResponse(status=204)

    body = ""
    announce = False
    if new:
        for entry in render_message_entries(
            new, _boundary_message(conversation, cursor)
        ):
            body += render_to_string(
                "comms/partials/message_entry.html", {"entry": entry}, request
            )
        body += render_to_string(
            "comms/partials/thread_cursor.html",
            {"thread_cursor": encode_cursor(new[-1]), "oob": True},
            request,
        )
        incoming = [message for message in new if message.sender_id != viewer.pk]
        if incoming:
            mark_conversation_read(
                user=viewer, conversation=conversation, up_to=new[-1].created_at
            )
            body += render_to_string(
                "comms/partials/thread_status.html",
                {"announcement": _incoming_announcement(incoming), "oob": True},
                request,
            )
            announce = True
    if flipped and request.GET.get("draft") == "0":
        if decision.allowed:
            body += render_to_string(
                "comms/partials/composer.html",
                {
                    "conversation": conversation,
                    "other": other,
                    "composer": _composer_context(
                        client_key=uuid4(), conversation=conversation
                    ),
                    "oob": True,
                },
                request,
            )
        else:
            heading, note = closed_note_copy(decision.reason, other)
            body += render_to_string(
                "comms/partials/closed_note.html",
                {"closed_heading": heading, "closed_body": note, "oob": True},
                request,
            )
    response = HttpResponse(body)
    if announce:
        response["HX-Trigger"] = CONVERSATION_CHANGED
    return response
