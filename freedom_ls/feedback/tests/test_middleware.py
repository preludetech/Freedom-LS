import json

import pytest

from django.http import HttpResponse
from django.test import RequestFactory

from freedom_ls.feedback.middleware import FeedbackMiddleware


def _make_middleware(response: HttpResponse | None = None) -> FeedbackMiddleware:
    """Create middleware with a simple get_response callable."""
    if response is None:
        response = HttpResponse("OK")
    return FeedbackMiddleware(lambda request: response)


@pytest.mark.django_db
def test_adds_hx_trigger_on_htmx_request_with_pending_feedback(
    rf: RequestFactory,
) -> None:
    """Middleware adds HX-Trigger header on HTMX requests when session has pending_feedback."""
    pending = {"form_id": "abc-123", "content_type_id": 1, "object_id": "xyz-456"}
    middleware = _make_middleware()

    request = rf.get("/", HTTP_HX_REQUEST="true")
    request.session = {"pending_feedback": pending}

    response = middleware(request)

    assert "HX-Trigger" in response
    triggers = json.loads(response["HX-Trigger"])
    assert triggers["show-feedback-modal"] == pending


@pytest.mark.django_db
def test_no_header_on_non_htmx_request(rf: RequestFactory) -> None:
    """Middleware does NOT add header on non-HTMX requests."""
    pending = {"form_id": "abc-123", "content_type_id": 1, "object_id": "xyz-456"}
    middleware = _make_middleware()

    request = rf.get("/")
    request.session = {"pending_feedback": pending}

    response = middleware(request)

    assert "HX-Trigger" not in response


@pytest.mark.django_db
def test_no_header_without_pending_feedback(rf: RequestFactory) -> None:
    """Middleware does NOT add header when no pending_feedback in session."""
    middleware = _make_middleware()

    request = rf.get("/", HTTP_HX_REQUEST="true")
    request.session = {}

    response = middleware(request)

    assert "HX-Trigger" not in response


@pytest.mark.django_db
def test_merges_with_existing_hx_trigger_json(rf: RequestFactory) -> None:
    """Middleware merges with existing JSON HX-Trigger headers."""
    pending = {"form_id": "abc-123", "content_type_id": 1, "object_id": "xyz-456"}
    existing_response = HttpResponse("OK")
    existing_response["HX-Trigger"] = json.dumps({"some-event": {"key": "value"}})
    middleware = _make_middleware(existing_response)

    request = rf.get("/", HTTP_HX_REQUEST="true")
    request.session = {"pending_feedback": pending}

    response = middleware(request)

    triggers = json.loads(response["HX-Trigger"])
    assert "some-event" in triggers
    assert triggers["show-feedback-modal"] == pending


@pytest.mark.django_db
def test_merges_with_existing_hx_trigger_string(rf: RequestFactory) -> None:
    """Middleware merges with existing string HX-Trigger headers."""
    pending = {"form_id": "abc-123", "content_type_id": 1, "object_id": "xyz-456"}
    existing_response = HttpResponse("OK")
    existing_response["HX-Trigger"] = "some-event"
    middleware = _make_middleware(existing_response)

    request = rf.get("/", HTTP_HX_REQUEST="true")
    request.session = {"pending_feedback": pending}

    response = middleware(request)

    triggers = json.loads(response["HX-Trigger"])
    assert "some-event" in triggers
    assert triggers["show-feedback-modal"] == pending
