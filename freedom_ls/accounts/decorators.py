"""View decorators for the accounts app."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps

from django.http import HttpRequest, HttpResponse
from django.http.response import HttpResponseBase
from django.utils.cache import add_never_cache_headers

from .utils import acquisition_auth_url, redirect_to_auth


def acquisition_login_required(
    view_func: Callable[..., HttpResponse],
) -> Callable[..., HttpResponse]:
    """login_required for acquisition calls to action.

    Same contract as login_required, but an anonymous visitor lands on
    acquisition_auth_url with next set, and an htmx request gets the
    HX-Redirect that redirect_to_auth produces.
    """

    @wraps(view_func)
    def _wrapped(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        return redirect_to_auth(
            request,
            next_url=request.get_full_path(),
            auth_url=acquisition_auth_url(request),
        )

    return _wrapped


def never_cache_same_origin(
    view_func: Callable[..., HttpResponseBase],
) -> Callable[..., HttpResponseBase]:
    """never_cache, plus a same-origin referrer policy.

    The pages this guards are reachable by session possession alone, so their
    URLs must not leak through a referrer or linger in a shared cache. The
    per-view header wins over SECURE_REFERRER_POLICY because SecurityMiddleware
    only sets a default.
    """

    @wraps(view_func)
    def _wrapped(
        request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponseBase:
        response = view_func(request, *args, **kwargs)
        add_never_cache_headers(response)
        response["Referrer-Policy"] = "same-origin"
        return response

    return _wrapped
