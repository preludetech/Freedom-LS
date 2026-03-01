import uuid
from copy import deepcopy
from xml.etree import ElementTree

# _load_icon is an internal API but the only way to get raw SVG Elements
# for custom attribute handling. Version is pinned to <3 in pyproject.toml.
from heroicons import _load_icon

from django import template
from django.utils.safestring import mark_safe

from freedom_ls.base.icons import ICONS

register = template.Library()


@register.simple_tag
def icon(name: str, variant: str = "outline", **kwargs: str) -> str:
    class_ = kwargs.get("class", "size-5")
    force_raw = kwargs.get("force", "")
    force = str(force_raw).lower() in ("true", "1", "yes") if force_raw else False
    aria_label = kwargs.get("aria_label", "") or None

    heroicon_name = ICONS[name] if not force else name  # KeyError if not in registry

    # Load the SVG element from the heroicons package
    svg = deepcopy(_load_icon(variant, heroicon_name))

    # Set CSS class
    svg.attrib["class"] = class_

    # Remove width/height so CSS classes control sizing
    svg.attrib.pop("width", None)
    svg.attrib.pop("height", None)

    # Accessibility attributes
    if aria_label:
        title_id = f"icon-title-{uuid.uuid4().hex[:8]}"
        svg.attrib["role"] = "img"
        svg.attrib["aria-labelledby"] = title_id
        svg.attrib.pop("aria-hidden", None)
        title_elem = ElementTree.SubElement(svg, "title")
        title_elem.text = aria_label
        title_elem.attrib["id"] = title_id
        # Move title to be the first child
        svg.remove(title_elem)
        svg.insert(0, title_elem)
    else:
        svg.attrib["aria-hidden"] = "true"

    result = ElementTree.tostring(svg, encoding="unicode")
    # Inline SVGs don't need xmlns
    result = result.replace(' xmlns="http://www.w3.org/2000/svg"', "", 1)

    return mark_safe(result)  # noqa: S308 - SVG from trusted heroicons package
