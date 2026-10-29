"""Template tags for the accounts app."""

from __future__ import annotations

from urllib.parse import urlencode

from allauth.account.utils import get_next_redirect_url, passthrough_next_redirect_url

from django import template
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.http import HttpRequest
from django.urls import Resolver404, resolve, reverse
from django.utils.http import url_has_allowed_host_and_scheme

register = template.Library()


@register.simple_tag(takes_context=True)
def url_with_next(context: template.Context, url_name: str, **query: str) -> str:
    """Reverse `url_name`, carrying the current request's safe `next` and any extra query params.

    Usage: {% url_with_next "account_signup" as signup_url %}
           {% url_with_next "account_signup" email=typed_email as signup_url %}

    Goes through allauth's own passthrough so these links and allauth's
    in-form links agree on which `next` values are safe. A falsy extra
    value (an empty typed email, say) is left off rather than added as
    `key=`.
    """
    url = reverse(url_name)
    request: HttpRequest | None = context.get("request")
    if request is not None:
        url = str(passthrough_next_redirect_url(request, url, REDIRECT_FIELD_NAME))
    extra = {key: value for key, value in query.items() if value}
    if not extra:
        return url
    return f"{url}{'&' if '?' in url else '?'}{urlencode(extra)}"


# Pages that never make sense to come back to: the auth pages themselves and
# the claim page, whose path is the credential.
_NO_RETURN_URL_NAME_PREFIX = "account_"
_NO_RETURN_VIEW_NAMES = frozenset({"course_applications:claim"})


def _request_next(context: template.Context) -> str | None:
    """The request's own safe `next`, or None."""
    request: HttpRequest | None = context.get("request")
    return get_next_redirect_url(request) if request is not None else None


def _is_no_return_path(path: str) -> bool:
    try:
        match = resolve(path)
    except Resolver404:
        return False
    url_name = match.url_name or ""
    return (
        url_name.startswith(_NO_RETURN_URL_NAME_PREFIX)
        or match.view_name in _NO_RETURN_VIEW_NAMES
    )


@register.simple_tag(takes_context=True)
def url_back_here(context: template.Context, url_name: str) -> str:
    """Reverse `url_name` carrying a `next` that brings the visitor back to this page.

    A `next` already on the request wins. Otherwise the current path is used,
    except where returning makes no sense: the home page, the account pages,
    the claim page and the error pages.
    """
    request: HttpRequest | None = context.get("request")
    url = reverse(url_name)
    if request is None:
        return url
    if _request_next(context):
        return url_with_next(context, url_name)
    if request.method != "GET" or context.get("is_error_page"):
        return url
    if request.path == "/" or _is_no_return_path(request.path):
        return url
    back = request.get_full_path()
    allowed = url_has_allowed_host_and_scheme(
        back, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    )
    if not allowed:
        return url
    return f"{url}?{urlencode({REDIRECT_FIELD_NAME: back})}"
