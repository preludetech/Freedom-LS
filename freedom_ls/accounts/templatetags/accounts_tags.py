"""Template tags for the accounts app."""

from __future__ import annotations

from allauth.account.utils import passthrough_next_redirect_url

from django import template
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.http import HttpRequest
from django.urls import reverse

register = template.Library()


@register.simple_tag(takes_context=True)
def url_with_next(context: template.Context, url_name: str) -> str:
    """Reverse `url_name`, carrying the current request's safe `next` along.

    Usage: {% url_with_next "account_signup" as signup_url %}

    Goes through allauth's own passthrough so these links and allauth's
    in-form links agree on which `next` values are safe.
    """
    url = reverse(url_name)
    request: HttpRequest | None = context.get("request")
    if request is None:
        return url
    return str(passthrough_next_redirect_url(request, url, REDIRECT_FIELD_NAME))
