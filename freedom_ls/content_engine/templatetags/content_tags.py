import re
from urllib.parse import urlparse

from django import template
from django.utils.html import escape
from django.utils.safestring import SafeString

from freedom_ls.content_engine.models import File, Form, Topic
from freedom_ls.markdown_rendering.markdown_utils import render_markdown

register = template.Library()

_FIRST_TABLE_RE = re.compile(r"<table[^>]*>", re.IGNORECASE)


@register.filter
def inject_table_caption(rendered_html: str, caption: str) -> SafeString:
    """Insert a ``<caption>`` as the first child of the first ``<table>``.

    The markdown ``tables`` extension emits no caption, so this splices one in
    to give the table a real, SR-associated accessible caption. The caption
    text is escaped (it is author input). If there is no ``<table>`` (or no
    caption), the input is returned unchanged.

    ``rendered_html`` is trusted markup straight from ``render_markdown``
    (already nh3-sanitised) and the only untrusted input (``caption``) is
    escaped, so the assembled string is safe to return as a ``SafeString``.
    """
    if not caption:
        # Safe: already sanitised by render_markdown.
        return SafeString(rendered_html)  # nosec B703 B308
    match = _FIRST_TABLE_RE.search(rendered_html)
    if not match:
        # Safe: already sanitised by render_markdown.
        return SafeString(rendered_html)  # nosec B703 B308
    caption_html = (
        f'<caption class="text-muted text-sm text-left px-3 py-2">'
        f"{escape(caption)}</caption>"
    )
    insert_at = match.end()
    # Safe: sanitised markup spliced with an escaped author caption.
    return SafeString(  # nosec B703 B308
        rendered_html[:insert_at] + caption_html + rendered_html[insert_at:]
    )


@register.filter
def safe_url(value: str | None) -> str:
    """Return ``value`` only when it is a safe link target.

    Permits http(s) URLs and relative URLs; blocks dangerous schemes
    (``javascript:``, ``data:``, ``vbscript:``, …) so author-supplied values
    can be emitted into URL attributes without smuggling executable content.

    The sole consumer is the non-navigable ``blockquote[cite]`` attribute, so a
    scheme-less (relative) value is treated as safe. If reused for a navigable
    attribute (``href``/``src``), scheme-relative ``//host`` values should be
    re-evaluated for that context.
    """
    if not value:
        return ""
    try:
        scheme = urlparse(value).scheme.lower()
    except ValueError:
        # Malformed input (e.g. an unterminated IPv6 literal) fails closed.
        return ""
    if scheme in ("", "http", "https"):
        return value
    return ""


@register.filter  # (needs_context=True)
def get_file_by_path(file_path, content_instance):
    """
    Template filter to look up a File object by its file_path.

    Usage: {{ "path/to/image.jpg"|get_file_by_path }}

    """

    if not file_path:
        return None
    file_path = file_path.strip()

    if not file_path:
        return None

    final_path = content_instance.calculate_path_from_root(file_path)

    try:
        return File.objects.get(file_path=final_path)
    except File.DoesNotExist:
        return None
    except File.MultipleObjectsReturned:
        # In case of duplicates, return the first one
        return File.objects.filter(file_path=final_path).first()


@register.simple_tag(takes_context=True)
def markdown(context, value):
    """
    Template tag to render markdown content.

    Usage: {% markdown content %}
    """
    request = context.get("request")
    return render_markdown(value, request)


@register.filter
def get_content_by_path(file_path, content_instance):
    """
    Template filter to look up a content object (Topic or Form) by its file_path.

    Usage: {{ "path/to/content.md"|get_content_by_path:content_instance }}
    """
    if not file_path:
        return None

    final_path = content_instance.calculate_path_from_root(file_path)

    # Try to find as Topic first
    try:
        return Topic.objects.get(file_path=final_path)
    except Topic.DoesNotExist:
        pass
    except Topic.MultipleObjectsReturned:
        return Topic.objects.filter(file_path=final_path).first()

    # Try to find as Form
    try:
        return Form.objects.get(file_path=final_path)
    except Form.DoesNotExist:
        pass
    except Form.MultipleObjectsReturned:
        return Form.objects.filter(file_path=final_path).first()

    return None
