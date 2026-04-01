"""Backward-compatible imports — rendering logic lives in backend.py."""

# TODO: remove this file, render_icon is only used in tests that can import from backend
from freedom_ls.icons.backend import DefaultIconBackend, _validate_svg_body

__all__ = ["_validate_svg_body", "render_icon"]

_default_backend = DefaultIconBackend()


def render_icon(
    semantic_name: str,
    variant: str = "outline",
    css_class: str = "size-5",
    aria_label: str = "",
) -> str:
    """Render an icon using the default backend. Kept for backward compatibility."""
    return _default_backend.render(
        semantic_name, variant=variant, css_class=css_class, aria_label=aria_label
    )
