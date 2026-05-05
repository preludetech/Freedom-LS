"""Base-app middleware.

`HtmxMessagesMiddleware` injects an out-of-band toast fragment into HTMX
responses that have queued Django messages, so server-produced messages
surface as toasts without a full-page reload. The same partial template
is used for full-page rendering and OOB injection so there is no second
source of truth for toast HTML.
"""

from __future__ import annotations

from collections.abc import Callable

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.template.loader import render_to_string


class HtmxMessagesMiddleware:
    """Append an OOB messages fragment to HTMX HTML responses.

    The middleware is a no-op for non-HTMX requests, redirects, non-HTML
    content types, streaming responses, and requests with no queued
    messages. When all preconditions are met it renders
    `partials/messages.html` in OOB mode and concatenates the result onto
    the response body.
    """

    def __init__(
        self,
        get_response: Callable[[HttpRequest], HttpResponse | StreamingHttpResponse],
    ) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse | StreamingHttpResponse:
        response = self.get_response(request)

        if request.headers.get("HX-Request") != "true":
            return response

        if isinstance(response, StreamingHttpResponse):
            return response

        # Redirects render messages on the next full-page load instead.
        if 300 <= response.status_code < 400:
            return response

        content_type = response.get("Content-Type", "")
        if "text/html" not in content_type:
            return response

        # `get_messages` returns an iterable that, when consumed, marks the
        # storage as used so the messages are cleared at the end of the
        # request cycle.
        storage = messages.get_messages(request)
        queued = list(storage)
        if not queued:
            return response

        fragment = render_to_string(
            "partials/messages.html",
            {"messages": queued, "oob": True},
            request=request,
        )

        response.content = response.content + fragment.encode("utf-8")
        if response.has_header("Content-Length"):
            response["Content-Length"] = str(len(response.content))
        return response
