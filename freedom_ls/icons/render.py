"""Generic icon resolver for the Freedom Learning System.

Provides a single source of truth for icon resolution that any app can use
without importing ``student_interface``.

The resolver walks the following resolution order:

1. ``icon`` empty -> render the ``default_semantic`` icon.
2. ``icon`` is a semantic name -> render via the icon backend.
3. ``icon`` is a literal glyph in the active icon set -> render that glyph.
4. ``icon_fallback`` (form ``<set>:<glyph>``) resolves -> render that glyph.
5. Otherwise -> render the ``default_semantic`` icon (graceful fallback).
"""

from __future__ import annotations

import re

from django.conf import settings
from django.utils.safestring import SafeString

from freedom_ls.icons.backend import build_svg, get_icon_backend
from freedom_ls.icons.loader import load_iconify_data
from freedom_ls.icons.mappings import ICON_SETS
from freedom_ls.icons.semantic_names import SEMANTIC_ICON_NAMES

_FALLBACK_RE = re.compile(r"^[a-z0-9_-]+:[a-z0-9_-]+$")


class IconResolutionError(RuntimeError):
    """Raised when a literal-glyph render expects a suffixed glyph that isn't present.

    Save-time validation should have caught this. Render time raises rather
    than silently falling back to the unsuffixed glyph because silent
    fallback hides regressions in the icon set.
    """


def _active_set_name() -> str:
    return settings.FREEDOM_LS_ICON_SET


def _render_literal(
    set_name: str,
    glyph: str,
    variant: str,
    css_class: str,
    aria_label: str,
) -> SafeString | None:
    """Render ``<set_name>:<glyph><variant_suffix>`` as an inline SVG.

    Returns ``None`` if the unsuffixed glyph is absent from the set's
    iconify JSON (caller should treat this as "not in this set, try
    next").

    Raises :class:`IconResolutionError` if the unsuffixed glyph is
    present but the suffixed form required by the variant is missing —
    a half-shipped icon set is loud, never silent.
    """
    if set_name not in ICON_SETS:
        return None
    config = ICON_SETS[set_name]
    if variant not in config.variants:
        # Unknown variants don't gracefully degrade — that's a programmer
        # error, not authored-content error.
        raise ValueError(
            f"Variant {variant!r} is not supported by icon set {set_name!r}. "
            f"Supported variants: {sorted(config.variants)}"
        )
    data = load_iconify_data(set_name)
    icons = data["icons"]
    if glyph not in icons:
        return None
    suffix = config.variants[variant]
    lookup = glyph + suffix if suffix else glyph
    if lookup not in icons:
        raise IconResolutionError(
            f"Glyph {glyph!r} variant {variant!r} expected suffixed name "
            f"{lookup!r} in icon set {set_name!r}, but it is missing."
        )
    return SafeString(  # nosec B703 - build_svg escapes attrs and validates body
        build_svg(
            set_name=set_name,
            lookup_name=lookup,
            css_class=css_class,
            aria_label=aria_label,
        )
    )


def render_icon(
    icon: str,
    icon_fallback: str = "",
    *,
    default_semantic: str,
    variant: str = "outline",
    css_class: str = "size-5",
    aria_label: str = "",
) -> SafeString:
    """Render an icon using a 5-step resolution order.

    Parameters
    ----------
    icon:
        The icon string — may be empty, a semantic name, or a literal glyph
        name from the active icon set.
    icon_fallback:
        An explicit ``<iconset>:<glyph>`` fallback used when ``icon`` does
        not resolve as a literal glyph in the active set.
    default_semantic:
        The semantic icon name to render when ``icon`` is empty (step 1) or
        when all resolution steps fail (step 5).
    variant:
        Icon variant (e.g. ``"outline"``, ``"solid"``).
    css_class:
        CSS class string applied to the ``<svg>`` element.
    aria_label:
        Accessible label. Defaults to the resolved name at each step.

    Returns a :class:`~django.utils.safestring.SafeString` of SVG markup.
    """
    icon = (icon or "").strip()
    icon_fallback = (icon_fallback or "").strip()
    backend = get_icon_backend()

    # 1. empty -> default semantic
    if not icon:
        return SafeString(  # nosec B703 - backend.render produces escaped SVG
            backend.render(
                default_semantic,
                variant=variant,
                css_class=css_class,
                aria_label=aria_label or default_semantic,
            )
        )

    # 2. semantic name
    if icon in SEMANTIC_ICON_NAMES:
        return SafeString(  # nosec B703 - backend.render produces escaped SVG
            backend.render(
                icon,
                variant=variant,
                css_class=css_class,
                aria_label=aria_label or icon,
            )
        )

    # 3. literal glyph in the active set
    active = _active_set_name()
    rendered = _render_literal(
        active,
        icon,
        variant,
        css_class,
        aria_label or icon,
    )
    if rendered is not None:
        return rendered

    # 4. explicit <iconset>:<glyph> fallback
    if icon_fallback and _FALLBACK_RE.match(icon_fallback):
        set_name, glyph = icon_fallback.split(":", 1)
        if set_name in ICON_SETS:
            rendered = _render_literal(
                set_name,
                glyph,
                variant,
                css_class,
                aria_label or glyph,
            )
            if rendered is not None:
                return rendered

    # 5. graceful default
    return SafeString(  # nosec B703 - backend.render produces escaped SVG
        backend.render(
            default_semantic,
            variant=variant,
            css_class=css_class,
            aria_label=aria_label or default_semantic,
        )
    )
