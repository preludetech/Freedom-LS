"""Base-app middleware.

`HtmxMessagesMiddleware` injects an out-of-band toast fragment into HTMX
responses that have queued Django messages, so server-produced messages
surface as toasts without a full-page reload. The same partial template
is used for full-page rendering and OOB injection so there is no second
source of truth for toast HTML.

`RemoveSlashMiddleware` is `CommonMiddleware`'s `APPEND_SLASH` in reverse: it
answers a 404 for a slashed path with a 301 to the slashless form when that
form resolves.
"""

from __future__ import annotations

from collections.abc import Callable

from django.contrib import messages
from django.contrib.messages.storage.base import BaseStorage
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponsePermanentRedirect,
    StreamingHttpResponse,
)
from django.template.loader import render_to_string
from django.urls import is_valid_path


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
        # If the view already iterated the storage (e.g. it rendered
        # partials/messages.html itself), those toasts are already in the
        # response body. Django 6.x's BaseStorage.__iter__ does not drain
        # _loaded_messages, so a second iteration here would re-emit the
        # same messages and produce duplicate OOB toasts.
        if isinstance(storage, BaseStorage) and storage.used:
            return response
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


class RemoveSlashMiddleware:
    """Answer a 404 for a slashed path with a 301 to its slashless form.

    `CommonMiddleware` only ever appends a slash, so a route with none
    (`/robots.txt`, `/sitemap.xml`, the learner form routes) 404s as soon as
    a browser, a chat app or a hand-typed link adds one. This is the same
    rule in the other direction. It fires only on a 404 whose path does not
    resolve but whose slashless form does, so it never turns a view's own
    404 into a redirect. It strips exactly one slash: a path ending in `//`
    is not a slip anyone makes, and redirecting it would hide a bad link.
    """

    def __init__(
        self,
        get_response: Callable[[HttpRequest], HttpResponse | StreamingHttpResponse],
    ) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse | StreamingHttpResponse:
        response = self.get_response(request)
        if response.status_code != 404 or not self.should_redirect_without_slash(
            request
        ):
            return response
        # `get_full_path` has already escaped the path and the query, so only
        # the slash goes.
        path, separator, query = request.get_full_path().partition("?")
        return HttpResponsePermanentRedirect(f"{path[:-1]}{separator}{query}")

    @staticmethod
    def should_redirect_without_slash(request: HttpRequest) -> bool:
        path = request.path_info
        if not path.endswith("/") or path.endswith("//"):
            return False
        urlconf = getattr(request, "urlconf", None)
        return not is_valid_path(path, urlconf) and bool(
            is_valid_path(path[:-1], urlconf)
        )
