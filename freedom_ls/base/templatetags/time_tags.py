from datetime import UTC, datetime

from django import template
from django.template import Context
from django.utils.html import format_html
from django.utils.safestring import SafeString

from freedom_ls.site_aware_models.time_zones import site_zone_text

register = template.Library()


@register.simple_tag(takes_context=True)
def local_time(context: Context, value: datetime) -> SafeString:
    """A <time> element the localTime Alpine component rewrites into the viewer's own zone.

    The server text is the site zone, labelled, so a page without JavaScript still says which
    zone it means. The datetime attribute carries the UTC instant the browser converts, to
    whole seconds: an end-of-day deadline falls at time.max, and six fraction digits are
    outside the date-time format a browser is promised to parse."""
    show_zone = "true" if context.get("show_time_zone_to_learners") else "false"
    return format_html(
        '<time datetime="{}" x-data="localTime" data-show-zone="{}">{}</time>',
        value.astimezone(UTC).isoformat(timespec="seconds"),
        show_zone,
        site_zone_text(value),
    )
