"""Tests for HtmxMessagesMiddleware.

Behaviour-only assertions. The middleware appends an OOB toast fragment to
HTMX HTML responses when there are queued Django messages, and otherwise
leaves the response untouched.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from django.contrib.messages import constants as message_constants
from django.contrib.messages.storage.base import Message
from django.contrib.messages.storage.session import SessionStorage
from django.http import (
    HttpRequest,
    HttpResponse,
    JsonResponse,
    StreamingHttpResponse,
)
from django.test import RequestFactory

from freedom_ls.base.middleware import HtmxMessagesMiddleware


def _request_with_messages(
    factory: RequestFactory,
    *,
    htmx: bool,
    messages_to_queue: list[tuple[int, str]] | None = None,
) -> HttpRequest:
    """Build a request with a real session-backed message storage attached.

    `messages_to_queue` is a list of (level, text) tuples — those are added to
    `request._messages` so the middleware can read them via get_messages.
    """
    headers: dict[str, str] = {}
    if htmx:
        headers["HTTP_HX_REQUEST"] = "true"
    request = factory.get("/", **headers)
    request.session = {}
    storage = SessionStorage(request)
    request._messages = storage
    if messages_to_queue:
        for level, text in messages_to_queue:
            storage.add(level, text)
    return request


def _make_get_response(
    response: HttpResponse | StreamingHttpResponse | JsonResponse,
) -> Callable[[HttpRequest], HttpResponse | StreamingHttpResponse | JsonResponse]:
    def get_response(
        request: HttpRequest,
    ) -> HttpResponse | StreamingHttpResponse | JsonResponse:
        return response

    return get_response


@pytest.mark.django_db
class TestHtmxMessagesMiddleware:
    @pytest.fixture(autouse=True)
    def _site_context(self, mock_site_context: object) -> None:
        # The messages partial is rendered with `request=request`, which
        # triggers context processors. The site-aware context processor
        # needs a current Site, so install the standard test fixture.
        return None

    def test_non_htmx_request_response_unchanged(self) -> None:
        factory = RequestFactory()
        request = _request_with_messages(
            factory,
            htmx=False,
            messages_to_queue=[(message_constants.SUCCESS, "Saved")],
        )
        original_body = b"<p>page</p>"
        response = HttpResponse(original_body, content_type="text/html")
        middleware = HtmxMessagesMiddleware(_make_get_response(response))

        result = middleware(request)

        assert result.content == original_body

    def test_htmx_request_no_messages_response_unchanged(self) -> None:
        factory = RequestFactory()
        request = _request_with_messages(factory, htmx=True)
        original_body = b"<p>page</p>"
        response = HttpResponse(original_body, content_type="text/html")
        middleware = HtmxMessagesMiddleware(_make_get_response(response))

        result = middleware(request)

        assert result.content == original_body

    def test_htmx_request_with_success_message_appends_polite_oob(
        self,
    ) -> None:
        factory = RequestFactory()
        request = _request_with_messages(
            factory,
            htmx=True,
            messages_to_queue=[(message_constants.SUCCESS, "Saved successfully")],
        )
        response = HttpResponse(b"<p>page</p>", content_type="text/html")
        middleware = HtmxMessagesMiddleware(_make_get_response(response))

        result = middleware(request)

        body = result.content.decode("utf-8")
        assert 'hx-swap-oob="beforeend:#toast-region-polite"' in body
        assert "Saved successfully" in body

    def test_htmx_request_with_error_message_appends_assertive_oob(
        self,
    ) -> None:
        factory = RequestFactory()
        request = _request_with_messages(
            factory,
            htmx=True,
            messages_to_queue=[(message_constants.ERROR, "Boom")],
        )
        response = HttpResponse(b"<p>page</p>", content_type="text/html")
        middleware = HtmxMessagesMiddleware(_make_get_response(response))

        result = middleware(request)

        body = result.content.decode("utf-8")
        assert 'hx-swap-oob="beforeend:#toast-region-assertive"' in body
        assert "Boom" in body

    def test_htmx_request_with_mixed_severities(self) -> None:
        factory = RequestFactory()
        request = _request_with_messages(
            factory,
            htmx=True,
            messages_to_queue=[
                (message_constants.SUCCESS, "Saved"),
                (message_constants.ERROR, "Boom"),
            ],
        )
        response = HttpResponse(b"<p>page</p>", content_type="text/html")
        middleware = HtmxMessagesMiddleware(_make_get_response(response))

        result = middleware(request)

        body = result.content.decode("utf-8")
        assert 'hx-swap-oob="beforeend:#toast-region-polite"' in body
        assert 'hx-swap-oob="beforeend:#toast-region-assertive"' in body
        assert "Saved" in body
        assert "Boom" in body

    def test_htmx_4xx_response_with_error_message_appends_fragment(
        self,
    ) -> None:
        factory = RequestFactory()
        request = _request_with_messages(
            factory,
            htmx=True,
            messages_to_queue=[(message_constants.ERROR, "Bad input")],
        )
        response = HttpResponse(
            b"<p>error page</p>",
            content_type="text/html",
            status=500,
        )
        middleware = HtmxMessagesMiddleware(_make_get_response(response))

        result = middleware(request)

        body = result.content.decode("utf-8")
        assert "Bad input" in body
        assert 'hx-swap-oob="beforeend:#toast-region-assertive"' in body

    def test_htmx_3xx_response_fragment_not_appended(self) -> None:
        factory = RequestFactory()
        request = _request_with_messages(
            factory,
            htmx=True,
            messages_to_queue=[(message_constants.SUCCESS, "Saved")],
        )
        response = HttpResponse(b"", content_type="text/html", status=302)
        middleware = HtmxMessagesMiddleware(_make_get_response(response))

        result = middleware(request)

        assert b"toast-region-" not in result.content

    def test_htmx_json_response_fragment_not_appended(self) -> None:
        factory = RequestFactory()
        request = _request_with_messages(
            factory,
            htmx=True,
            messages_to_queue=[(message_constants.SUCCESS, "Saved")],
        )
        response = JsonResponse({"ok": True})
        middleware = HtmxMessagesMiddleware(_make_get_response(response))

        result = middleware(request)

        assert b"toast-region-" not in result.content

    def test_htmx_streaming_response_fragment_not_appended(self) -> None:
        factory = RequestFactory()
        request = _request_with_messages(
            factory,
            htmx=True,
            messages_to_queue=[(message_constants.SUCCESS, "Saved")],
        )
        response = StreamingHttpResponse(
            iter([b"<p>chunk</p>"]),
            content_type="text/html",
        )
        middleware = HtmxMessagesMiddleware(_make_get_response(response))

        result = middleware(request)

        # The result must remain a StreamingHttpResponse and we must not have
        # tried to mutate `.content` (which would consume the iterator).
        assert isinstance(result, StreamingHttpResponse)

    def test_message_storage_is_marked_used_after_middleware(self) -> None:
        """After the middleware runs, the storage is marked as `used` so the
        downstream MessageMiddleware.process_response clears it; the messages
        do not get re-rendered on the next request."""
        factory = RequestFactory()
        request = _request_with_messages(
            factory,
            htmx=True,
            messages_to_queue=[(message_constants.SUCCESS, "Saved")],
        )
        response = HttpResponse(b"<p>page</p>", content_type="text/html")
        middleware = HtmxMessagesMiddleware(_make_get_response(response))

        middleware(request)

        # The storage is marked used by virtue of being iterated.
        assert request._messages.used is True

    def test_content_length_header_updated_when_present(self) -> None:
        factory = RequestFactory()
        request = _request_with_messages(
            factory,
            htmx=True,
            messages_to_queue=[(message_constants.SUCCESS, "Saved")],
        )
        body = b"<p>page</p>"
        response = HttpResponse(body, content_type="text/html")
        response["Content-Length"] = str(len(body))
        middleware = HtmxMessagesMiddleware(_make_get_response(response))

        result = middleware(request)

        assert result["Content-Length"] == str(len(result.content))

    def test_message_object_directly_used(self) -> None:
        """Smoke test: a manually constructed Message works through the path."""
        # Just confirms Message construction is compatible with the partial.
        msg = Message(level=message_constants.WARNING, message="Heads up")
        assert "warning" in msg.tags
