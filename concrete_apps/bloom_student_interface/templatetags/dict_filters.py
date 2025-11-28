from django import template

register = template.Library()


@register.filter
def dict_get(dictionary, key):
    """
    Simple dictionary dict_get filter.
    Usage: {{ mydict|dict_get:key }}
    Equivalent to: mydict.get(key, {})
    """
    if dictionary is None:
        return {}
    return dictionary.get(key, {})
