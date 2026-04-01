import functools
import re

from django.conf import settings
from django.utils.html import escape
from django.utils.module_loading import import_string

from freedom_ls.icons.loader import load_iconify_data
from freedom_ls.icons.mappings import ICON_SETS

_DANGEROUS_SVG_PATTERN = re.compile(r"<script|<foreignObject|on\w+\s*=", re.IGNORECASE)


def _validate_svg_body(body: str) -> str:
    """Reject SVG bodies that contain potentially dangerous content."""
    if _DANGEROUS_SVG_PATTERN.search(body):
        raise ValueError("SVG body contains potentially dangerous content")
    return body


class IconBackend:
    """Base class for custom icon backends."""

    def render(
        self,
        semantic_name: str,
        variant: str = "outline",
        css_class: str = "size-5",
        aria_label: str = "",
    ) -> str:
        raise NotImplementedError("Subclasses must implement render()")


class DefaultIconBackend(IconBackend):
    """Default backend that renders icons from iconify JSON data."""

    def render(
        self,
        semantic_name: str,
        variant: str = "outline",
        css_class: str = "size-5",
        aria_label: str = "",
    ) -> str:
        # No caching needed: getattr on settings is trivial, and
        # load_iconify_data() already caches its result.
        icon_set_name: str = getattr(settings, "FREEDOM_LS_ICON_SET", "heroicons")
        overrides: dict[str, str] = getattr(settings, "FREEDOM_LS_ICON_OVERRIDES", {})

        set_config = ICON_SETS[icon_set_name]
        mapping = {**set_config.mapping, **overrides}
        icon_name = mapping[semantic_name]

        if variant not in set_config.variants:
            supported = sorted(set_config.variants)
            raise ValueError(
                f"Variant {variant!r} is not supported by icon set {icon_set_name!r}. "
                f"Supported variants: {supported}"
            )

        variant_suffix = set_config.variants[variant]
        lookup_name = (
            icon_name + variant_suffix if variant_suffix is not None else icon_name
        )

        data = load_iconify_data(icon_set_name)
        icons = data["icons"]
        if lookup_name not in icons:
            raise KeyError(
                f"Icon '{lookup_name}' not found in '{icon_set_name}' Iconify JSON "
                f"(semantic_name={semantic_name!r}, variant={variant!r})"
            )
        icon_data = icons[lookup_name]

        body = _validate_svg_body(icon_data["body"])
        width = int(icon_data.get("width", data.get("width", 24)))
        height = int(icon_data.get("height", data.get("height", 24)))

        label = escape(aria_label if aria_label else semantic_name)

        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'class="inline {escape(css_class)}" role="img" aria-label="{label}">'
            f"{body}</svg>"
        )


@functools.cache
def get_icon_backend() -> IconBackend:
    """Return the configured icon backend, or the default backend.

    Result is cached for the process lifetime. In tests that use
    ``override_settings(FREEDOM_LS_ICON_BACKEND=...)``, call
    ``get_icon_backend.cache_clear()`` before and after the test.
    """
    backend_path: str | None = getattr(settings, "FREEDOM_LS_ICON_BACKEND", None)
    if backend_path is None:
        return DefaultIconBackend()
    backend_class: type[IconBackend] = import_string(backend_path)
    return backend_class()
