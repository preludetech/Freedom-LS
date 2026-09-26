"""View decorators for the accounts app."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps

from django.http import HttpRequest, HttpResponse

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
