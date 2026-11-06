from datetime import UTC, datetime
from typing import Literal

from django import template
from django.template import Context
from django.utils.html import format_html, format_html_join
from django.utils.safestring import SafeString

from freedom_ls.site_aware_models.time_zones import has_set_time, site_zone_text

register = template.Library()

FORMATS = ("", "short")


@register.simple_tag(takes_context=True)
def local_time(
    context: Context, value: datetime, format: Literal["", "short"] = ""
) -> SafeString:
    """A <time> element the localTime Alpine component rewrites into the viewer's own zone.

    The server text is the site zone, labelled, so a page without JavaScript still says which
    zone it means. The datetime attribute carries the UTC instant the browser converts, to
    whole seconds: an end-of-day deadline falls at time.max, and six fraction digits are
    outside the date-time format a browser is promised to parse.

    "short" asks the browser for the day and month only, or "Today" when the instant falls on
    the viewer's own date, plus the time when the deadline has one (data-timed)."""
    if format not in FORMATS:
        raise ValueError(f"local_time format must be one of {FORMATS}, not {format!r}.")
    instant = value.astimezone(UTC).isoformat(timespec="seconds")
    show_zone = "true" if context.get("show_time_zone_to_learners") else "false"
    attrs: list[tuple[str, str]] = []
    if format == "short":
        attrs.append(("data-format", "short"))
        if has_set_time(value):
            attrs.append(("data-timed", "true"))
    return format_html(
        '<time datetime="{}" x-data="localTime" data-show-zone="{}"{}>{}</time>',
        instant,
        show_zone,
        format_html_join("", ' {}="{}"', attrs),
        site_zone_text(value, short=format == "short"),
    )
