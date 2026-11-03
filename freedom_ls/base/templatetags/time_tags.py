from datetime import UTC, datetime

from django import template
from django.template import Context
from django.utils.html import format_html
from django.utils.safestring import SafeString

from freedom_ls.site_aware_models.time_zones import site_zone_text

register = template.Library()


@register.simple_tag(takes_context=True)
def local_time(context: Context, value: datetime, format: str = "") -> SafeString:
    """A <time> element the localTime Alpine component rewrites into the viewer's own zone.

    The server text is the site zone, labelled, so a page without JavaScript still says which
    zone it means. The datetime attribute carries the UTC instant the browser converts, to
    whole seconds: an end-of-day deadline falls at time.max, and six fraction digits are
    outside the date-time format a browser is promised to parse.

    "short" asks the browser for the day and month only; "today" is a fixed word, left
    alone by the browser because the server already decided it is today in the site zone."""
    instant = value.astimezone(UTC).isoformat(timespec="seconds")
    if format == "today":
        return format_html('<time datetime="{}">Today</time>', instant)
    show_zone = "true" if context.get("show_time_zone_to_learners") else "false"
    format_attr = format_html(' data-format="{}"', format) if format == "short" else ""
    return format_html(
        '<time datetime="{}" x-data="localTime" data-show-zone="{}"{}>{}</time>',
        instant,
        show_zone,
        format_attr,
        site_zone_text(value, short=format == "short"),
    )
