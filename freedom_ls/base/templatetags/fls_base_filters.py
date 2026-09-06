from datetime import timedelta

from django import template
from django.utils import timezone
from django.utils.timesince import timesince

register = template.Library()


@register.filter
def duration(value: timedelta) -> str:
    """
    Template filter to render a timedelta as human-readable text, e.g. "1 hour".

    Usage: {{ my_timedelta|duration }}
    """
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
