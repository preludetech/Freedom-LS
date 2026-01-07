from django import template
from django.template.defaultfilters import stringfilter

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
