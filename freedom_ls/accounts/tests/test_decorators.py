"""Tests for the accounts view decorators."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse

from freedom_ls.accounts.decorators import never_cache_same_origin


@never_cache_same_origin
def _view(request: HttpRequest) -> HttpResponse:
    return HttpResponse("ok")


def test_never_cache_same_origin_sets_no_store():
    response = _view(HttpRequest())

    assert "no-store" in response["Cache-Control"]


def test_never_cache_same_origin_sets_same_origin_referrer_policy():
    response = _view(HttpRequest())

    assert response["Referrer-Policy"] == "same-origin"
