from datetime import timedelta

from django import template
from django.utils import timezone
from django.utils.html import avoid_wrapping
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

    Usage: {{ my_dict|get_dict_item:my_key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)
