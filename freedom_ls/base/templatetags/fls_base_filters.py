import json
from datetime import timedelta

from django import template
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from django.utils.html import avoid_wrapping, format_html
from django.utils.safestring import SafeString, mark_safe
from django.utils.timesince import timesince
from django.utils.translation import ngettext

register = template.Library()


@register.filter
def duration(value: object) -> str:
    """
    Template filter to render a timedelta as human-readable text, e.g. "1 hour".

    `timesince` floors to whole minutes, so it renders anything shorter than a
    minute as "0 minutes", which reads as though the wait is already over.
    Sub-minute values are spelled out in seconds here instead, formatted the
    way `timesince` formats its own units so the two read alike.

    The parameter is `object` rather than `timedelta` because a template can
    hand a filter anything; anything else renders as the empty string, the way
    a Django filter handed the wrong type does, rather than raising mid-render.

    Usage: {{ my_timedelta|duration }}
    """
    if not isinstance(value, timedelta):
        return ""

    seconds = int(value.total_seconds())
    if seconds < 60:
        return avoid_wrapping(
            ngettext("%(num)d second", "%(num)d seconds", seconds) % {"num": seconds}
        )

    now = timezone.now()
    return timesince(now, now + value)


@register.filter
def get_dict_item(dictionary, key):
    """
    Template filter to get an item from a dictionary by key.

    A template variable that was never added to the context resolves to the
    empty string, not `None`, so a template that has not been handed the dict
    at all must not crash the render either.

    Usage: {{ my_dict|get_dict_item:my_key }}
    """
    if not isinstance(dictionary, dict):
        return None
    return dictionary.get(key)


# Django's own escape table for `json_script` is private
# (`django.utils.html._json_script_escapes`), so it is reproduced here.
_JSON_LD_ESCAPES = {ord("<"): "\\u003C", ord(">"): "\\u003E", ord("&"): "\\u0026"}


@register.filter(is_safe=True)
def json_ld_script(value: object, element_id: str) -> SafeString:
    """
    Serialise `value` as JSON-LD, wrapped in a <script type="application/ld+json"> tag.

    Structured data must use "application/ld+json" -- the type schema.org
    crawlers look for. `django.utils.html.json_script` renders the same
    payload as "application/json" instead, which is why this filter exists
    rather than reusing it directly.

    Usage: {{ my_dict|json_ld_script:"course-jsonld" }}
    """
    _payload = json.dumps(value, cls=DjangoJSONEncoder).translate(_JSON_LD_ESCAPES)
    _tag_template = '<script id="{}" type="application/ld+json">{}</script>'
    # The payload is escaped with json_script's own table above.
    return format_html(_tag_template, element_id, mark_safe(_payload))  # noqa: S308  # nosec B308 B703
