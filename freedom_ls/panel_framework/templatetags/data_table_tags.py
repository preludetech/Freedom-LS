from django import template

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


@register.filter
def is_blank(value: object) -> bool:
    """
    True when value is None, empty, or contains only whitespace once stringified.

    Usage: {% if object|getattr_str:column.text_attr|is_blank %}
    """
    if value is None:
        return True

    return not str(value).strip()


@register.simple_tag
def link_cell_text(obj: object, text_attr: str, fallback_text_attr: str = "") -> object:
    """
    The link cell's text: text_attr, or fallback_text_attr when that is blank.

    Usage: {% link_cell_text object column.text_attr column.fallback_text_attr as cell_text %}
    """
    text = getattr_str(obj, text_attr)
    if is_blank(text) and fallback_text_attr:
        return getattr_str(obj, fallback_text_attr)
    return text
