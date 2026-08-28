"""Tests for `CurrentSiteMiddleware`'s handling of the ambient request.

The thread local itself is what is under test here, so these tests plant and
inspect it directly rather than going through `mock_site_context`.
"""

from __future__ import annotations

import pytest

from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

from freedom_ls.site_aware_models.middleware import CurrentSiteMiddleware
from freedom_ls.site_aware_models.models import _thread_locals


@pytest.fixture
def request_factory() -> RequestFactory:
    return RequestFactory()


def test_an_outer_request_is_restored_after_a_nested_call(
    request_factory: RequestFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A request already on the thread is back in place once the middleware returns."""
    outer = request_factory.get("/outer/")
    monkeypatch.setattr(_thread_locals, "request", outer, raising=False)

    inner = request_factory.get("/inner/")
    seen: list[HttpRequest] = []

    def get_response(request: HttpRequest) -> HttpResponse:
        seen.append(getattr(_thread_locals, "request", None))
        return HttpResponse()

    CurrentSiteMiddleware(get_response)(inner)

    assert seen == [inner]
    assert _thread_locals.request is outer


def test_the_thread_local_is_cleared_when_nothing_was_ambient(
    request_factory: RequestFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no request on the thread beforehand, none is left behind."""
    monkeypatch.delattr(_thread_locals, "request", raising=False)

    CurrentSiteMiddleware(lambda request: HttpResponse())(request_factory.get("/"))

    assert not hasattr(_thread_locals, "request")


def test_an_outer_request_is_restored_when_the_view_raises(
    request_factory: RequestFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An exception below the middleware must not leave the wrong request behind."""
    outer = request_factory.get("/outer/")
    monkeypatch.setattr(_thread_locals, "request", outer, raising=False)

    def get_response(request: HttpRequest) -> HttpResponse:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        CurrentSiteMiddleware(get_response)(request_factory.get("/inner/"))

    assert _thread_locals.request is outer


def test_the_thread_local_is_cleared_when_the_view_raises(
    request_factory: RequestFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An exception with nothing ambient beforehand leaks nothing onto the thread."""
    monkeypatch.delattr(_thread_locals, "request", raising=False)

    def get_response(request: HttpRequest) -> HttpResponse:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        CurrentSiteMiddleware(get_response)(request_factory.get("/"))

    assert not hasattr(_thread_locals, "request")
