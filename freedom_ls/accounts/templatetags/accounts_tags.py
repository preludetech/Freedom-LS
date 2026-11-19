"""Template tags for the accounts app."""

from __future__ import annotations

from urllib.parse import urlencode

from allauth.account.utils import passthrough_next_redirect_url

from django import template
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.http import HttpRequest
from django.urls import reverse

from freedom_ls.accounts.sidebar import CurrentSidebarEntry, sidebar_entries

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


@register.simple_tag(takes_context=True)
def account_sidebar_entries(context: template.Context) -> list[CurrentSidebarEntry]:
    """The account area's sidebar entries, with the current page marked."""
    return sidebar_entries(context["request"])
