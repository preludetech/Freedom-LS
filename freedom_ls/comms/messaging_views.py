"""Direct-message views: the thread page and sending into it."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

from django.contrib.sites.models import Site
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from freedom_ls.comms.config import config
from freedom_ls.comms.messaging import (
    SendResult,
    latest_page,
    other_participant,
    refusal_alert_copy,
    send_message,
)
from freedom_ls.comms.models import Conversation
from freedom_ls.comms.views import messaging_view
from freedom_ls.site_aware_models.models import get_cached_site

if TYPE_CHECKING:
    from freedom_ls.accounts.models import User


def participant_conversation(request: HttpRequest, pk: UUID) -> Conversation:
    """The conversation ``pk`` if the signed-in user takes part in it, else 404.

    The site-aware manager hides another site's conversations, so a pk from
    another site is a 404 as well.
    """
    return cast(
        "Conversation",
        get_object_or_404(
            Conversation.objects.filter(participants__user=request.user), pk=pk
        ),
    )


def _composer_context(
    *, client_key: UUID, draft: str = "", alert: str = ""
) -> dict[str, object]:
    return {
        "client_key": client_key,
        "draft": draft,
        "alert": alert,
        "max_length": config.MESSAGE_MAX_LENGTH,
    }


def thread_context(
    request: HttpRequest, conversation: Conversation
) -> dict[str, object]:
    viewer = cast("User", request.user)
    return {
        "conversation": conversation,
        "other": other_participant(conversation, viewer),
        "thread_messages": latest_page(conversation),
        "composer": _composer_context(client_key=uuid4()),
        "page_size": config.MESSAGE_PAGE_SIZE,
    }


@messaging_view
def thread(request: HttpRequest, pk: UUID) -> HttpResponse:
    conversation = participant_conversation(request, pk)
    return render(request, "comms/thread.html", thread_context(request, conversation))


def _send_response(
    request: HttpRequest,
    result: SendResult,
    conversation: Conversation,
    draft: str,
    client_key: UUID,
) -> HttpResponse:
    """The answer to a send, shared by every view that posts a message.

    A stored message answers with its log entry plus a fresh composer swapped in
    out of band. A refusal or body error answers 422 with the composer holding
    the draft, the same key and the reason; the retarget headers point the
    global 422 swap at the composer instead of the log.
    """
    viewer = cast("User", request.user)
    other = other_participant(conversation, viewer)
    if result.message is not None:
        if request.headers.get("HX-Request") != "true":
            return redirect("conversations:thread", pk=conversation.pk)
        body = render_to_string(
            "comms/partials/message_entry.html",
            {"message": result.message, "conversation": conversation},
            request,
        )
        body += render_to_string(
            "comms/partials/composer.html",
            {
                "conversation": conversation,
                "other": other,
                "composer": _composer_context(client_key=uuid4()),
                "oob": True,
            },
            request,
        )
        return HttpResponse(body)

    alert = result.body_error or refusal_alert_copy(result.refusal, other)
    context = {
        "conversation": conversation,
        "other": other,
        "composer": _composer_context(client_key=client_key, draft=draft, alert=alert),
    }
    if request.headers.get("HX-Request") != "true":
        return render(
            request,
            "comms/thread.html",
            {**thread_context(request, conversation), **context},
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
