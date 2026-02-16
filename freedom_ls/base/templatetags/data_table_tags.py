import re

from django import template
from django.urls import reverse

register = template.Library()


@register.filter
def getattr_str(obj, attr_name: str):
    """
    Get an attribute from an object using a string attribute name.
    Supports nested attributes with dot notation (e.g., 'user.email').
    If the result is callable, it will be called automatically.

    Usage: {{ object|getattr_str:"field_name" }}
           {{ object|getattr_str:"related.field_name" }}
           {{ object|getattr_str:"__str__" }}
    """
    if not attr_name:
        return obj

    try:
        # Support nested attribute access with dot notation
        for part in attr_name.split("."):
            obj = getattr(obj, part)

        # If the result is callable (like a method), call it
        if callable(obj):
            obj = obj()

        return obj
    except (AttributeError, TypeError):
        return None


@register.simple_tag
def resolve_url_path_template(obj: object, url_name: str, path_template: str) -> str:
    """Build a URL by substituting {attr} placeholders in the path template
    with attribute values from the object, then reversing the URL.

    Usage: {% resolve_url_path_template object "educator_interface:interface" "cohorts/{pk}" %}
    Produces: /educator/cohorts/42
    """
    def replace_attr(match: re.Match[str]) -> str:
        attr_name = match.group(1)
        value = obj
        for part in attr_name.split("."):
            value = getattr(value, part)
        if callable(value):
            value = value()
        return str(value)

    path_string = re.sub(r"\{(\w+(?:\.\w+)*)\}", replace_attr, path_template)
    return reverse(url_name, kwargs={"path_string": path_string})
