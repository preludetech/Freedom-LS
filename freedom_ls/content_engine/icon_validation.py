"""Validation rules for ``Course.icon`` and ``Course.icon_fallback``.

These rules are applied at content-save time (via
:meth:`Course.clean`) and mirrored on the pydantic ``Course`` schema so
``content_validate`` rejects bad content before it ever reaches the
database.

The validator is a pure function so it can be reused by both the model
and the pydantic ``model_validator``.
"""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError

from freedom_ls.icons.loader import load_iconify_data
from freedom_ls.icons.mappings import ICON_SETS
from freedom_ls.icons.semantic_names import SEMANTIC_ICON_NAMES

_FALLBACK_RE = re.compile(r"^[a-z0-9_-]+:[a-z0-9_-]+$")


def _validate_fallback_shape_and_target(icon_fallback: str) -> None:
    """Validate the ``<set>:<glyph>`` fallback against its own set.

    Raises :class:`~django.core.exceptions.ValidationError` on any
    structural problem, unknown set, missing glyph, or missing variant
    suffix.
    """
    if not _FALLBACK_RE.match(icon_fallback):
        raise ValidationError(
            {
                "icon_fallback": (
                    "icon_fallback must match '<iconset>:<glyph>' using only "
                    "lowercase letters, digits, underscores, and hyphens "
                    f"(got {icon_fallback!r})."
                )
            }
        )
    set_name, glyph = icon_fallback.split(":", 1)
    if set_name not in ICON_SETS:
        raise ValidationError(
            {
                "icon_fallback": (
                    f"icon_fallback names unknown icon set {set_name!r}. "
                    f"Known sets: {sorted(ICON_SETS)}."
                )
            }
        )
    try:
        data = load_iconify_data(set_name)
    except (ValueError, FileNotFoundError) as exc:
        raise ValidationError(
            {
                "icon_fallback": (
                    f"icon_fallback references icon set {set_name!r}, but its "
                    f"iconify JSON could not be loaded: {exc}"
                )
            }
        ) from exc
    icons = data.get("icons", {})
    if glyph not in icons:
        raise ValidationError(
            {
                "icon_fallback": (
                    f"icon_fallback glyph {glyph!r} not found in icon set {set_name!r}."
                )
            }
        )
    config = ICON_SETS[set_name]
    missing = [
        variant
        for variant, suffix in config.variants.items()
        if suffix is not None and (glyph + suffix) not in icons
    ]
    if missing:
        raise ValidationError(
            {
                "icon_fallback": (
                    f"icon_fallback glyph {glyph!r} in {set_name!r} is missing "
                    f"variant glyphs: {missing}. The icon set ships variants "
                    f"that do not include this glyph; cross-set fallback would "
                    f"render inconsistently."
                )
            }
        )


def validate_course_icon_fields(icon: str, icon_fallback: str) -> None:
    """Validate the ``icon`` / ``icon_fallback`` pair on a Course.

    Empty strings are normalised. Rules:

    * Both empty: OK (default ``"course"`` semantic icon will render).
    * ``icon`` empty, ``icon_fallback`` set: error.
    * ``icon`` is a semantic name: OK; ``icon_fallback`` (if set) must
      still be structurally valid because it's still authored data.
    * ``icon`` is a literal glyph: must exist in at least one registered
      icon set, and every set that contains the unsuffixed glyph must
      also contain the suffixed forms required by its variants.
    * ``icon_fallback`` is validated against the named set.
    """
    icon = (icon or "").strip()
    icon_fallback = (icon_fallback or "").strip()

    if not icon and not icon_fallback:
        return

    if not icon and icon_fallback:
        raise ValidationError(
            {
                "icon_fallback": (
                    "icon_fallback set without icon. Set 'icon' to either a "
                    "semantic name or a literal glyph; icon_fallback is only "
                    "consulted when 'icon' fails to resolve in the active "
                    "icon set."
                )
            }
        )

    # icon set: semantic OR must be a literal glyph in at least one
    # registered set.
    if icon in SEMANTIC_ICON_NAMES:
        if icon_fallback:
            _validate_fallback_shape_and_target(icon_fallback)
        return

    # Literal glyph path. We have no idea which icon set will be active
    # at render time (theme-driven), so we validate against every set
    # that ships this glyph.
    sets_with_glyph: list[str] = []
    variant_problems: list[str] = []
    for set_name, config in ICON_SETS.items():
        try:
            data = load_iconify_data(set_name)
        except (ValueError, FileNotFoundError):
            continue
        icons = data.get("icons", {})
        if icon not in icons:
            continue
        sets_with_glyph.append(set_name)
        for variant_name, suffix in config.variants.items():
            if suffix is None:
                continue
            if (icon + suffix) not in icons:
                variant_problems.append(f"{set_name}:{variant_name}")

    if not sets_with_glyph:
        raise ValidationError(
            {
                "icon": (
                    f"icon {icon!r} is not a semantic name and is not present "
                    f"in any registered icon set. Use one of "
                    f"{sorted(SEMANTIC_ICON_NAMES)}, or a literal glyph name "
                    f"that exists in at least one of {sorted(ICON_SETS)}."
                )
            }
        )

    if variant_problems:
        raise ValidationError(
            {
                "icon": (
                    f"icon {icon!r} is missing variant glyph(s): "
                    f"{variant_problems}. The icon set has the unsuffixed "
                    f"glyph but is missing one or more suffixed variants. "
                    f"Pick a different glyph or fix the icon set."
                )
            }
        )

    if icon_fallback:
        _validate_fallback_shape_and_target(icon_fallback)
