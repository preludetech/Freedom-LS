import re

from django.conf import settings
from django.utils.html import escape

from freedom_ls.icons.loader import load_iconify_data
from freedom_ls.icons.mappings import ICON_SETS

_DANGEROUS_SVG_PATTERN = re.compile(r"<script|<foreignObject|on\w+\s*=", re.IGNORECASE)


def _validate_svg_body(body: str) -> str:
    """Reject SVG bodies that contain potentially dangerous content."""
    if _DANGEROUS_SVG_PATTERN.search(body):
        raise ValueError("SVG body contains potentially dangerous content")
    return body


def render_icon(
    semantic_name: str,
    variant: str = "outline",
    css_class: str = "size-5",
    aria_label: str = "",
) -> str:
    """Resolve a semantic icon name and render it as inline SVG HTML."""
    icon_set_name: str = getattr(settings, "FREEDOM_LS_ICON_SET", "heroicons")
    overrides: dict[str, str] = getattr(settings, "FREEDOM_LS_ICON_OVERRIDES", {})

    set_config = ICON_SETS[icon_set_name]
    mapping = {**set_config.mapping, **overrides}
    icon_name = mapping[semantic_name]

    # Validate variant is supported by this icon set
    if variant not in set_config.variants:
        supported = sorted(set_config.variants)
        raise ValueError(
            f"Variant {variant!r} is not supported by icon set {icon_set_name!r}. "
            f"Supported variants: {supported}"
        )

    variant_suffix = set_config.variants[variant]
    if variant_suffix is not None:
        lookup_name = icon_name + variant_suffix
    else:
        lookup_name = icon_name

    data = load_iconify_data(icon_set_name)
    icon_data = data["icons"][lookup_name]

    body = _validate_svg_body(icon_data["body"])
    width = icon_data.get("width", data.get("width", 24))
    height = icon_data.get("height", data.get("height", 24))

    label = escape(aria_label if aria_label else semantic_name)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'class="inline {escape(css_class)}" role="img" aria-label="{label}">'
        f"{body}</svg>"
    )
