from django import template
from django.utils.http import urlencode

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


@register.simple_tag
def column_badge(obj: object, column: object) -> object:
    """The badge a `BadgeColumn` shows for a row, or None for no badge.

    Usage: {% column_badge object column as badge %}
    """
    badge = getattr(column, "badge", None)
    return badge(obj) if callable(badge) else None


@register.simple_tag
def pagination_suffix(
    sort_by: str = "",
    sort_order: str = "",
    search_query: str = "",
    extra_params: str = "",
) -> str:
    """Build the trailing query-string suffix used by ``<c-pagination />``.

    Returns a string like ``"&sort=name&order=asc&search=alice"`` —
    intentionally with the leading ``&`` so it can sit directly after
    ``?page=N`` in a URL without further conditionals at the call site.

    ``extra_params`` is expected to be a pre-joined ``a=b&c=d`` fragment
    (typically built via ``join_query`` so it's already URL-encoded). It is
    appended verbatim.
    """
    params: dict[str, str] = {}
    if sort_by:
        params["sort"] = sort_by
        params["order"] = sort_order or "asc"
    if search_query:
        params["search"] = search_query
    encoded = urlencode(params)
    pieces = [piece for piece in (encoded, extra_params) if piece]
    if not pieces:
        return ""
    return "&" + "&".join(pieces)
