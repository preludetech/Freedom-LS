import re
import warnings
from pathlib import Path

from coloraide import Color

_VAR_RE = re.compile(r"var\(\s*(--[\w-]+)\s*\)")

# Maximum substitution depth for var() resolution, to guard against deep chains.
_MAX_VAR_DEPTH = 50


class ColorResolveError(Exception):
    """Raised when a raw CSS colour cannot be resolved to hex."""


def parse_tailwind_tokens(css_file_path: str) -> dict[str, str]:
    """Parse all CSS custom properties from a CSS file.

    Returns a dict keyed by the full custom-property name minus the leading
    ``--``, e.g. ``{"color-primary": "#2B6CB0", "fls-radius-md": "0.375rem"}``.
    All values are returned as-is (raw strings) — no filtering or conversion.

    Raises FileNotFoundError if the file does not exist.
    """
    path = Path(css_file_path)
    if not path.exists():
        raise FileNotFoundError(f"CSS file not found: {css_file_path}")

    content = path.read_text()
    pattern = re.compile(r"--([\w-]+)\s*:\s*([^;]+);")
    return {name: value.strip() for name, value in pattern.findall(content)}


def parse_tailwind_colors(css_file_path: str) -> dict[str, str]:
    """Parse --color-* custom properties from a CSS file.

    Returns a dict like ``{"primary": "#2B6CB0", "on-surface": "#1A2332", ...}``.
    All color values are captured as raw strings (hex, rgb, hsl, oklch, etc.).

    This is a thin back-compat filter over ``parse_tailwind_tokens``.
    Raises FileNotFoundError if the file does not exist.
    """
    all_tokens = parse_tailwind_tokens(css_file_path)
    prefix = "color-"
    return {
        name[len(prefix) :]: value
        for name, value in all_tokens.items()
        if name.startswith(prefix)
    }


def _expand_vars(raw: str, token_map: dict[str, str]) -> str:
    """Substitute all var(--x) references from token_map.

    Raises ColorResolveError on an unknown variable or a reference cycle.
    """
    seen: set[str] = set()
    current = raw
    for _ in range(_MAX_VAR_DEPTH):
        match = _VAR_RE.search(current)
        if match is None:
            return current
        full_prop = match.group(1)  # e.g. "--color-primary"
        key = full_prop.lstrip("-")  # e.g. "color-primary"
        if key not in token_map:
            raise ColorResolveError(f"Unknown CSS variable {full_prop!r} in {raw!r}")
        if key in seen:
            raise ColorResolveError(
                f"Cyclic CSS variable reference involving {full_prop!r}"
            )
        seen.add(key)
        replacement = token_map[key]
        current = current[: match.start()] + replacement + current[match.end() :]
    # Exceeded depth — treat as a cycle
    raise ColorResolveError(
        f"Exceeded maximum var() substitution depth resolving {raw!r}"
    )


def _split_top_level_commas(s: str) -> list[str]:
    """Split a string on commas that are not inside parentheses."""
    parts: list[str] = []
    depth = 0
    start = 0
    for i, ch in enumerate(s):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(s[start:i].strip())
            start = i + 1
    parts.append(s[start:].strip())
    return parts


def _resolve_color_mix(value: str, token_map: dict[str, str]) -> str:
    """Resolve a color-mix(in <space>, A [p1%], B [p2%]) expression to #rrggbb.

    Raises ColorResolveError on any parse or conversion failure.
    """
    # Strip outer color-mix(...) wrapper
    inner_match = re.match(r"color-mix\(\s*(.*)\s*\)\s*$", value, re.DOTALL)
    if not inner_match:
        raise ColorResolveError(f"Cannot parse color-mix expression: {value!r}")
    inner = inner_match.group(1).strip()

    parts = _split_top_level_commas(inner)
    if len(parts) != 3:
        raise ColorResolveError(
            f"Expected 3 comma-separated parts in color-mix, got {len(parts)}: {value!r}"
        )

    space_part, a_part, b_part = parts

    # Parse the color space (e.g. "in oklch" -> "oklch")
    space_match = re.match(r"in\s+([\w-]+)", space_part.strip())
    if not space_match:
        raise ColorResolveError(
            f"Cannot parse color space from {space_part!r} in {value!r}"
        )
    space = space_match.group(1)

    def _parse_color_arg(arg: str) -> tuple[str, float | None]:
        """Split a color arg into (color_str, percentage | None)."""
        pct_match = re.search(r"\s+([\d.]+)%\s*$", arg)
        if pct_match:
            pct = float(pct_match.group(1))
            color_str = arg[: pct_match.start()].strip()
        else:
            pct = None
            color_str = arg.strip()
        return color_str, pct

    a_str, a_pct = _parse_color_arg(a_part)
    b_str, b_pct = _parse_color_arg(b_part)

    # Recursively resolve each colour operand (handles var() and nested color-mix)
    a_resolved = resolve_css_color(_expand_vars(a_str, token_map), token_map)
    b_resolved = resolve_css_color(_expand_vars(b_str, token_map), token_map)

    # Compute coloraide's mix weight (B's weight in the blend).
    # CSS color-mix rule: if only one percentage p is given, A gets p and B
    # gets 100-p. If neither, 50/50. coloraide mix(b, weight=w) takes B's weight.
    if a_pct is not None and b_pct is not None:
        b_weight = b_pct / 100.0
    elif a_pct is not None:
        b_weight = (100.0 - a_pct) / 100.0
    elif b_pct is not None:
        b_weight = b_pct / 100.0
    else:
        b_weight = 0.5

    try:
        mixed = Color(a_resolved).mix(
            b_resolved, space=space, weight=b_weight, powerless=True
        )
        return mixed.convert("srgb").to_string(hex=True)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ColorResolveError(
            f"color-mix conversion failed for {value!r}: {exc}"
        ) from exc


def resolve_css_color(raw: str, token_map: dict[str, str]) -> str:
    """Resolve a raw CSS color value to a 6-digit #rrggbb hex string.

    Handles hex (3/4/6/8-digit), rgb/rgba, hsl/hsla, oklch, oklab, lch, lab,
    named colors, var() references, and color-mix() expressions.

    Raises ColorResolveError on any parse, cycle, or conversion failure.
    """
    try:
        resolved = _expand_vars(raw.strip(), token_map)
    except ColorResolveError:
        raise

    resolved = resolved.strip()

    if resolved.startswith("color-mix("):
        return _resolve_color_mix(resolved, token_map)

    try:
        return Color(resolved).convert("srgb").to_string(hex=True)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ColorResolveError(
            f"Cannot convert {resolved!r} (from {raw!r}) to hex: {exc}"
        ) from exc


_CSS_KEYWORDS: frozenset[str] = frozenset(
    {
        "system-ui",
        "ui-sans-serif",
        "ui-monospace",
        "-apple-system",
    }
)

_WEB_SAFE_ALLOWLIST: frozenset[str] = frozenset(
    {
        "arial",
        "helvetica",
        "helvetica neue",
        "verdana",
        "georgia",
        "times new roman",
        "courier new",
        "trebuchet ms",
        "tahoma",
    }
)

_GENERIC_FAMILIES: frozenset[str] = frozenset({"sans-serif", "serif", "monospace"})


def _is_css_keyword(name: str) -> bool:
    """Return True if the name is a CSS keyword (system font or ui-* variant)."""
    lower = name.lower()
    if lower in _CSS_KEYWORDS:
        return True
    # Drop any ui-* keyword not in the explicit set
    return bool(lower.startswith("ui-"))


def email_safe_font_stack(raw_font_sans: str) -> str:
    """Filter a CSS font-family stack to email-safe names only.

    Drops CSS system-font keywords (system-ui, ui-sans-serif, ui-monospace,
    -apple-system, and any other ui-* keywords) and custom font names not on
    the web-safe allowlist. Always preserves or appends a generic family
    (sans-serif, serif, or monospace). Multi-word names are re-quoted.

    Emits a UserWarning when only a generic family remains but at least one
    custom (non-keyword, non-allowlisted) name was stripped.
    """
    # Normalise line continuations / extra whitespace within the value
    normalised = " ".join(raw_font_sans.split())

    parts = _split_top_level_commas(normalised)

    kept: list[str] = []
    had_custom = False
    trailing_generic: str | None = None

    for part in parts:
        # Strip surrounding whitespace and quotes for classification
        stripped = part.strip()
        unquoted = stripped.strip('"').strip("'").strip()
        lower = unquoted.lower()

        if lower in _GENERIC_FAMILIES:
            trailing_generic = lower
            continue

        if _is_css_keyword(unquoted):
            continue

        if lower in _WEB_SAFE_ALLOWLIST:
            # Re-quote multi-word names
            if " " in unquoted:
                kept.append(f'"{unquoted}"')
            else:
                kept.append(unquoted)
        else:
            # Custom font — not email-safe; note that it was present
            had_custom = True

    # Determine the generic to append/keep
    generic = trailing_generic or "sans-serif"

    result_parts = [*kept, generic]
    result = ", ".join(result_parts)

    if had_custom and not kept:
        warnings.warn(
            f"Font stack {raw_font_sans!r} contains only custom fonts not in the "
            f"email-safe allowlist; falling back to {generic!r} only.",
            UserWarning,
            stacklevel=2,
        )

    return result


def extract_font_family(
    token_map: dict[str, str], fallback: str = "Arial, Helvetica, sans-serif"
) -> str:
    """Extract an email-safe font-family stack from the theme token map.

    Returns ``email_safe_font_stack(token_map["fls-font-sans"])`` when the
    token is present. If it is absent, emits a UserWarning and returns
    *fallback* unchanged.
    """
    if "fls-font-sans" in token_map:
        return email_safe_font_stack(token_map["fls-font-sans"])
    warnings.warn(
        "Theme token --fls-font-sans not found; using fallback font family.",
        UserWarning,
        stacklevel=2,
    )
    return fallback


def extract_button_radius(token_map: dict[str, str], fallback: str = "6px") -> str:
    """Extract the button border-radius value from the theme token map.

    Returns the raw value of ``--fls-radius-md`` as-is (e.g. ``'0.375rem'``,
    ``'0.5rem'``, ``'6px'``). If the token is absent, emits a UserWarning and
    returns *fallback*.
    """
    if "fls-radius-md" in token_map:
        return token_map["fls-radius-md"]
    warnings.warn(
        "Theme token --fls-radius-md not found; using fallback button radius.",
        UserWarning,
        stacklevel=2,
    )
    return fallback


def resolve_color_token(token_map: dict[str, str], token: str, fallback: str) -> str:
    """Resolve ``color-<token>`` from the token map to a #rrggbb hex string.

    If the token is missing, or if the raw value cannot be resolved, a
    UserWarning is emitted and the fallback is returned. Never raises.
    """
    raw = token_map.get(f"color-{token}")
    if raw is None:
        warnings.warn(
            f"Email colour token --color-{token} not found; using fallback {fallback}.",
            UserWarning,
            stacklevel=2,
        )
        return fallback
    try:
        return resolve_css_color(raw, token_map)
    except (ColorResolveError, ValueError) as exc:
        warnings.warn(
            f"Email colour token --color-{token}={raw!r} could not be resolved "
            f"({exc}); using fallback {fallback}.",
            UserWarning,
            stacklevel=2,
        )
        return fallback
