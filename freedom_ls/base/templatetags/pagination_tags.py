from django import template
from django.utils.http import urlencode

register = template.Library()


@register.simple_tag
def join_query(**kwargs: str | int) -> str:
    """Join keyword arguments into a ``&``-separated query-string fragment.

    Used at the call sites of ``<c-pagination />`` to build the
    ``extra_params`` input from a few unrelated values without forcing each
    template to do its own ``stringformat:'s' | add:...`` chains. Values are
    URL-encoded so callers can pass UUIDs, ints, or arbitrary strings without
    worrying about ``&``/``=``/whitespace breaking the URL.
    """
    return urlencode({k: str(v) for k, v in kwargs.items()})


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
