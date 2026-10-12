"""View decorators for the accounts app."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps

from django.http import HttpRequest, HttpResponse

from .utils import redirect_to_acquisition_auth


def acquisition_login_required(
    view_func: Callable[..., HttpResponse],
) -> Callable[..., HttpResponse]:
    """login_required for acquisition calls to action.

    Same contract as login_required, but an anonymous visitor gets what
    redirect_to_acquisition_auth produces.
    """

    @wraps(view_func)
    def _wrapped(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        return redirect_to_acquisition_auth(request)

    return _wrapped
