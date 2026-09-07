import uuid

from django import template
from django.http import HttpRequest

register = template.Library()


@register.simple_tag
def unique_id(prefix: str = "id") -> str:
    """Generate a unique ID for use in HTML elements.

    Usage: {% unique_id "modal-title" as my_id %}
    Then use {{ my_id }} in id= and aria-labelledby= attributes.
    """
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@register.simple_tag
def toast_uid() -> str:
    """Generate a unique hex id used as the DOM id for a toast element.

    Usage: {% toast_uid as uid %}
    Then use {{ uid }} in id="toast-{{ uid }}".
    """
    return uuid.uuid4().hex


@register.simple_tag(takes_context=True)
def canonical_url(context: template.Context) -> str:
    """Absolute URL for the current page, with the query string stripped.

    Usage: {% canonical_url as canonical_url %}

    Returns an empty string when the template is rendered without a request.
    """
    request: HttpRequest | None = context.get("request")
    if request is None:
        return ""
    return request.build_absolute_uri(request.path)
