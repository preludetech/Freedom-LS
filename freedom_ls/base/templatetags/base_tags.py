import uuid

from django import template

register = template.Library()


@register.simple_tag
def unique_id(prefix: str = "id") -> str:
    """Generate a unique ID for use in HTML elements.

    Usage: {% unique_id "modal-title" as my_id %}
    Then use {{ my_id }} in id= and aria-labelledby= attributes.
    """
    return f"{prefix}-{uuid.uuid4().hex[:8]}"
