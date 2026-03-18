import re

from django import template
from django.urls import reverse

register = template.Library()


@register.simple_tag
def resolve_url_path_template(obj: object, url_name: str, path_template: str) -> str:
    """Build a URL by substituting {attr} placeholders in the path template
    with attribute values from the object, then reversing the URL.

    Usage: {% resolve_url_path_template object "educator_interface:interface" "cohorts/{pk}" %}
    Produces: /educator/cohorts/42
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
    return reverse(url_name, kwargs={"path_string": path_string})
