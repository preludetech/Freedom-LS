import re
import uuid
import zlib

from django import template
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.safestring import SafeString

from freedom_ls.panel_framework.actions import PanelAction
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.panels import Panel

register = template.Library()

TONES = frozenset({"success", "warning", "error", "info", "muted"})
HEADING_LEVELS = frozenset({"1", "2", "3", "4", "5", "6"})


@register.filter
def tone(value: str) -> str:
    """Map an arbitrary tone value onto one of `c-chip`'s status variants.

    `primary` and `secondary` are chip variants but not tones, so they fall
    back to `muted` along with anything else unrecognised.
    """
    return value if value in TONES else "muted"


@register.filter
def heading_level(value: str, default: str) -> str:
    """Fall back to `default` unless `value` is a heading level 1-6."""
    return value if str(value) in HEADING_LEVELS else default


@register.filter
def clamp_percentage(value: int | float | str) -> int:
    """Clamp a percentage to the 0-100 range the progress bar can render."""
    return min(100, max(0, int(float(value))))


@register.filter
def avatar_slot(value: int | str | uuid.UUID) -> int:
    """Pick one of six avatar colour slots for `value`.

    `crc32` (unlike `hash()`) is stable across processes, so the same id
    always lands in the same slot for every request and every worker.
    """
    return zlib.crc32(str(value).encode()) % 6 + 1


@register.filter
def initials(name: str) -> str:
    """Derive avatar initials from the first and last words of `name`.

    One word gives one letter, and an empty name gives none.
    """
    words = str(name).split()
    if not words:
        return ""
    letters = words[0][0] if len(words) == 1 else words[0][0] + words[-1][0]
    return letters.upper()


@register.filter
def times(value: int | str) -> range:
    """Turn an integer (or a numeric string) into a range for `{% for %}`."""
    return range(int(value))


@register.simple_tag
def render_panel(panel: Panel) -> SafeString:
    """Render a bound panel through its own template and context.

    `{% include %}` cannot take a context dict, so this tag is how a template
    renders another panel. It renders against the panel's own request, so
    context processors run as they would for a page.
    """
    return render_to_string(
        panel.template_name, panel.get_context_data(), request=panel.request
    )


@register.simple_tag
def render_action(action: PanelAction, ctx: PanelContext) -> SafeString:
    """Render an action for the panel or view whose context is `ctx`."""
    return render_to_string(
        action.template_name, action.get_context_data(ctx), request=ctx.request
    )


@register.simple_tag(takes_context=True)
def resolve_url_path_template(
    context: template.Context, obj: object, url_name: str, path_template: str
) -> str:
    """Build a URL by substituting {attr} placeholders in the path template
    with attribute values from the object, then reversing the URL.

    Usage: {% resolve_url_path_template object "educator_interface:interface" "cohorts/{pk}" %}
    Produces: /educator/cohorts/42

    Merges in request.panel_url_kwargs — the same extra reverse() kwargs a
    hosting view supplies to the menu and breadcrumb builders — so a link
    built from a table cell carries whatever scope segment the current
    request needs, without this tag ever knowing what that segment means.
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
    request = context.get("request")
    extra_url_kwargs: dict[str, str] = getattr(request, "panel_url_kwargs", {})
    return reverse(url_name, kwargs={"path_string": path_string, **extra_url_kwargs})
