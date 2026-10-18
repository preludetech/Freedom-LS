"""Direct-message views: the thread page and sending into it."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

from django.contrib.sites.models import Site
from django.core.exceptions import BadRequest
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
    latest_messages,
    latest_page,
    mark_conversation_read,
    messages_after,
    new_messages_announcement,
    other_participant,
    page_before,
    refusal_alert_copy,
    render_message_entries,
    reply_decision,
    reply_decisions,
    search_recipients,
    send_message,
    unreachable_recipient_alert_copy,
    unread_conversation_count,
)
from freedom_ls.comms.messaging_loader import get_messaging_policy
from freedom_ls.comms.models import Conversation, Message
from freedom_ls.comms.views import messaging_view
from freedom_ls.site_aware_models.models import get_cached_site

if TYPE_CHECKING:
    from django.db.models import QuerySet


# The composer's character counter appears this many characters before the limit.
COUNTER_MARGIN = 200

CONVERSATION_CHANGED = json.dumps({"conversationChanged": {}})

# The id of the region a quick-view composer swaps, which is also the value
# htmx sends in ``HX-Target`` when a send comes from there.
QUICK_VIEW_BOX_ID = "quick-view-message-box"

# How many of the conversation's newest messages the quick-view box shows.
QUICK_VIEW_MESSAGE_COUNT = 3


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
    conversations = list(inbox_for(user))
    decisions = reply_decisions(viewer=user, conversations=conversations)
    return [
        InboxRow(
            conversation,
            other_participant(conversation, user),
            decisions[conversation.pk].allowed,
        )
        for conversation in conversations
    ]


def inbox_state(rows: list[InboxRow]) -> str:
    """A token that changes whenever a row would render differently.

    It covers each row's newest message, its unread flag and whether the
    viewer can reply, so a read marker moving or a conversation closing
    refreshes the list as well as a new message does.
    """
    parts = [
        f"{row.conversation.pk}:{row.conversation.last_message_at}:"
        f"{getattr(row.conversation, 'is_unread', False)}:{row.can_reply}"
        for row in rows
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def _inbox_context(
    request: HttpRequest, current: Conversation | None = None
) -> dict[str, object]:
    rows = inbox_rows(cast("User", request.user))
    return {
        "inbox_rows": rows,
        "inbox_state": inbox_state(rows),
        "inbox_poll_seconds": config.MESSAGE_INBOX_POLL_SECONDS,
        "current_pk": current.pk if current is not None else None,
    }


def composer_context(
    *,
    client_key: UUID,
    draft: str = "",
    alert: str = "",
    conversation: Conversation | None = None,
    recipient: User | None = None,
    action_url: str | None = None,
    in_modal: bool = False,
    in_quick_view: bool = False,
) -> dict[str, object]:
    """What the composer partial needs.

    A composer for an existing conversation posts to its ``send`` URL and
    appends the new message to the log. A composer for a first message posts to
    ``start`` with the recipient, and replaces itself when refused. ``action_url``
    posts somewhere else instead, and ``in_modal`` makes the answer replace the
    whole app modal body, which is where a first message composed in the modal
    sends its refusal. ``in_quick_view`` makes the answer replace the quick-view
    box instead, so the drawer around it stays open.
    """
    if action_url is None:
        if conversation is not None:
            action_url = reverse("conversations:send", kwargs={"pk": conversation.pk})
        else:
            action_url = reverse("conversations:start")
    return {
        "client_key": client_key,
        "draft": draft,
        "alert": alert,
        "max_length": config.MESSAGE_MAX_LENGTH,
        "counter_from": max(0, config.MESSAGE_MAX_LENGTH - COUNTER_MARGIN),
        "action_url": action_url,
        "recipient": recipient,
        "in_modal": in_modal,
        "in_quick_view": in_quick_view,
    }


def message_box_context(
    *,
    conversation: Conversation | None,
    other: User | None,
    client_key: UUID,
    draft: str = "",
    alert: str = "",
    recipient: User | None = None,
) -> dict[str, object]:
    """What the quick-view message box partial needs.

    The box shows the conversation's newest messages and a composer. Without a
    conversation yet the composer starts one with ``recipient``.
    """
    messages = (
        latest_messages(conversation, QUICK_VIEW_MESSAGE_COUNT)
        if conversation is not None
        else []
    )
    return {
        "conversation": conversation,
        "other": other,
        "box_entries": render_message_entries(messages, None),
        "composer": composer_context(
            client_key=client_key,
            draft=draft,
            alert=alert,
            conversation=conversation,
            recipient=recipient,
            in_quick_view=True,
        ),
    }


def thread_context(
    request: HttpRequest, conversation: Conversation
) -> dict[str, object]:
    """What the thread partial needs, and marks the conversation read.

    The marker moves to the newest message on the page, not to now, so a message
    that lands between this render and the mark stays unread.
    """
    viewer = cast("User", request.user)
    other = other_participant(conversation, viewer)
    decision = reply_decision(viewer=viewer, conversation=conversation)
    shown, has_older = latest_page(conversation)
    closed_heading, closed_body = ("", "")
    if not decision.allowed:
        closed_heading, closed_body = closed_note_copy(decision.reason, other)
    if shown:
        mark_conversation_read(
            user=viewer, conversation=conversation, up_to=shown[-1].created_at
        )
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
        "composer": composer_context(client_key=uuid4(), conversation=conversation),
        "page_size": config.MESSAGE_PAGE_SIZE,
        "back_url": reverse("conversations:inbox"),
    }


@messaging_view
def thread(request: HttpRequest, pk: UUID) -> HttpResponse:
    conversation = participant_conversation(request, pk)
    context = thread_context(request, conversation)
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
    """The refreshed conversation list, or 204 when no row changed.

    The page sends the state token of the list it shows (``state``) and the pk
    of the open thread (``current``), which keeps ``aria-current`` on that row.
    A missing or stale token re-renders the list.
    """
    viewer = cast("User", request.user)
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
    if request.GET.get("state") == context["inbox_state"]:
        return HttpResponse(status=204)
    context["has_recipients"] = _has_recipients(request)
    body = render_to_string(
        "comms/partials/conversation_list.html#conversation-list", context, request
    )
    body += render_to_string(
        "comms/partials/inbox_state.html", {**context, "oob": True}, request
    )
    return HttpResponse(body)


def _quick_view_box_response(
    request: HttpRequest,
    result: SendResult,
    conversation: Conversation | None,
    draft: str,
    client_key: UUID,
    recipient: User | None,
) -> HttpResponse:
    """The answer to a send from the quick-view box: the box itself, replaced.

    A stored message answers 200 with the newest messages and a fresh composer,
    and tells the page the conversation changed. A refusal or body error answers
    422 with the box holding the draft and the reason. The request already
    targets the box, so no retarget header is needed and the drawer stays open.
    """
    viewer = cast("User", request.user)
    if result.message is not None:
        conversation = cast("Conversation", result.conversation)
        other = other_participant(conversation, viewer)
        context = message_box_context(
            conversation=conversation, other=other, client_key=uuid4()
        )
        response = HttpResponse(
            render_to_string("comms/partials/message_box.html", context, request)
        )
        response["HX-Trigger"] = CONVERSATION_CHANGED
        return response
    other = (
        recipient if conversation is None else other_participant(conversation, viewer)
    )
    context = message_box_context(
        conversation=conversation,
        other=other,
        client_key=client_key,
        draft=draft,
        alert=result.body_error or refusal_alert_copy(result.refusal, other),
        recipient=recipient,
    )
    return HttpResponse(
        render_to_string("comms/partials/message_box.html", context, request),
        status=422,
    )


def unreachable_recipient_response(request: HttpRequest) -> HttpResponse:
    """A 422 for a recipient the sender isn't offered, the same whoever the pk is.

    Only the composer's alert is replaced, so the draft and the name already
    on screen stay put and nothing here says who the pk belongs to.
    """
    response = HttpResponse(
        render_to_string(
            "comms/partials/composer.html#error",
            {"composer": {"alert": unreachable_recipient_alert_copy()}},
            request,
        ),
        status=422,
    )
    response["HX-Retarget"] = "#composer-error"
    response["HX-Reswap"] = "outerHTML"
    return response


def _send_response(
    request: HttpRequest,
    result: SendResult,
    conversation: Conversation | None,
    draft: str,
    client_key: UUID,
    recipient: User | None = None,
) -> HttpResponse:
    """The answer to a send, shared by every view that posts a message.

    A stored message in an existing thread answers with every entry newer than
    the page's cursor (``after``), so a message that arrived since the last
    poll is not skipped, plus a fresh composer swapped in out of band. Without
    a cursor it answers with the new message's entry alone. A first message (``recipient`` set)
    answers by loading the new thread. A refusal or body error answers 422 with
    the composer holding the draft, the same key and the reason; the retarget
    headers point the global 422 swap at the composer instead of the log.
    """
    viewer = cast("User", request.user)
    is_htmx = request.headers.get("HX-Request") == "true"
    if is_htmx and request.headers.get("HX-Target") == QUICK_VIEW_BOX_ID:
        return _quick_view_box_response(
            request, result, conversation, draft, client_key, recipient
        )
    if result.message is not None:
        sent_to = cast("Conversation", result.conversation)
        thread_url = reverse("conversations:thread", kwargs={"pk": sent_to.pk})
        if not is_htmx:
            return redirect(thread_url)
        if recipient is not None:
            response = HttpResponse(status=204)
            response["HX-Location"] = json.dumps({"path": thread_url})
            return response
        cursor = decode_cursor(request.POST.get("after", ""))
        new = messages_after(sent_to, cursor) if cursor is not None else []
        if new:
            body, _ = _appended_entries(request, sent_to, new, cursor)
        else:
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
                "composer": composer_context(client_key=uuid4(), conversation=sent_to),
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
        "composer": composer_context(
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
    client_key = posted_client_key(request)
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


def posted_client_key(request: HttpRequest) -> UUID:
    """The send's ``client_key`` from the POST body; a 400 when it is not a UUID."""
    try:
        return UUID(request.POST.get("client_key", ""))
    except ValueError:
        raise BadRequest("client_key must be a UUID") from None


def recipient_pk(raw: str | None) -> int:
    """A posted or queried recipient id; a 404 when it is not an integer."""
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
    recipient = get_object_or_404(_offered_recipients(request), pk=recipient_pk(raw))
    return render(
        request,
        "comms/start.html",
        {
            "recipient": recipient,
            "other": recipient,
            "composer": composer_context(client_key=uuid4(), recipient=recipient),
        },
    )


def _start_post(request: HttpRequest) -> HttpResponse:
    client_key = posted_client_key(request)
    draft = request.POST.get("body", "")
    site = cast("Site", get_cached_site(request))
    recipient = (
        _offered_recipients(request)
        .filter(pk=recipient_pk(request.POST.get("recipient")))
        .first()
    )
    if recipient is None:
        if request.headers.get("HX-Request") != "true":
            # A full page can't keep the draft without naming the person.
            raise Http404("recipient not offered")
        return unreachable_recipient_response(request)
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
    boundary_message = _boundary_message(conversation, cursor)
    body = ""
    for entry in render_message_entries(older, None):
        body += render_to_string(
            "comms/partials/message_entry.html", {"entry": entry}, request
        )
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


def _incoming_announcement(incoming: list[Message]) -> str:
    sender = incoming[-1].sender
    name = sender.display_name if sender is not None else "Deleted user"
    return new_messages_announcement(len(incoming), name)


def _appended_entries(
    request: HttpRequest,
    conversation: Conversation,
    new: list[Message],
    cursor: tuple[datetime, UUID] | None,
) -> tuple[str, bool]:
    """Log entries for ``new``, which follow the message ``cursor`` names.

    The cursor moves out of band to the last of them. When some came from the
    other participant, the thread is marked read up to the last one and the
    screen-reader announcement is swapped in; the flag says whether it was.
    """
    viewer = cast("User", request.user)
    body = ""
    for entry in render_message_entries(new, _boundary_message(conversation, cursor)):
        body += render_to_string(
            "comms/partials/message_entry.html", {"entry": entry}, request
        )
    body += render_to_string(
        "comms/partials/thread_cursor.html",
        {"thread_cursor": encode_cursor(new[-1]), "oob": True},
        request,
    )
    incoming = [message for message in new if message.sender_id != viewer.pk]
    if not incoming:
        return body, False
    mark_conversation_read(
        user=viewer, conversation=conversation, up_to=new[-1].created_at
    )
    body += render_to_string(
        "comms/partials/thread_status.html",
        {"announcement": _incoming_announcement(incoming), "oob": True},
        request,
    )
    return body, True


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
        body, announce = _appended_entries(request, conversation, new, cursor)
    if flipped and request.GET.get("draft") == "0":
        if decision.allowed:
            body += render_to_string(
                "comms/partials/composer.html",
                {
                    "conversation": conversation,
                    "other": other,
                    "composer": composer_context(
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
