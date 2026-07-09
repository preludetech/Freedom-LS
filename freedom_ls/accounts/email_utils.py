import functools
import re
import struct
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from coloraide import Color

# Display height (px) the email header logo is scaled to. The width is derived
# from the logo's real aspect ratio so the image is never stretched.
EMAIL_LOGO_DISPLAY_HEIGHT = 48

_VAR_RE = re.compile(r"var\(\s*(--[\w-]+)\s*\)")

# Maximum substitution depth for var() resolution, to guard against deep chains.
_MAX_VAR_DEPTH = 50

# A CSS length literal: a bare `0`, or a number with a unit (e.g. 6px,
# 0.375rem, 50%). A unitless non-zero number is invalid CSS, so it is rejected.
# The button radius is interpolated into an email <style> block; constraining it
# to a length keeps a malformed theme value from injecting CSS, mirroring how
# colours are validated to #rrggbb and the font stack is allowlist-constrained.
_LENGTH_RE = re.compile(r"^(0|\d*\.?\d+(px|rem|em|%))$")

# Slug of the theme that ships with FLS and provides the baseline token values.
# get_email_theme parses this theme's theme.css as the single source of default
# colours/font/radius, then layers the active theme on top — so there are no
# hardcoded values here to drift from the default theme.
DEFAULT_THEME_SLUG = "default"

# The email colour roles resolved from the theme, each mapped to the EmailTheme
# field it backs. The role key is looked up as `--color-<role>` in the merged
# token map; the field is the EmailTheme attribute (the two differ only for
# `on-surface`, which backs `color_foreground`). The header band has its own
# role so a theme can paint it independently of `primary` (e.g. first_class uses
# a white header); the default theme aliases it to `primary`/`on-primary`.
EMAIL_COLOR_ROLES: tuple[tuple[str, str], ...] = (
    ("primary", "color_primary"),
    ("on-primary", "color_on_primary"),
    ("on-surface", "color_foreground"),
    ("muted", "color_muted"),
    ("surface", "color_surface"),
    ("surface-2", "color_surface_2"),
    ("border", "color_border"),
    ("header", "color_header"),
    ("on-header", "color_on_header"),
)


class EmailThemeError(Exception):
    """Raised when an email theme token cannot be resolved from the theme."""


class ColorResolveError(EmailThemeError):
    """Raised when a raw CSS colour cannot be resolved to hex."""


def parse_tailwind_tokens(css_file_path: str) -> dict[str, str]:
    """Parse all CSS custom properties from a CSS file.

    Returns a dict keyed by the full custom-property name minus the leading
    ``--``, e.g. ``{"color-primary": "#2B6CB0", "fls-radius-md": "0.375rem"}``.
    All values are returned as-is (raw strings) — no filtering or conversion.

    Matches every ``--<name>`` declaration in the file; if a token is declared
    more than once (e.g. a dark-mode re-declaration) the last occurrence wins.
    The email tokens are assumed to be defined exactly once in the active theme.

    Raises FileNotFoundError if the file does not exist.
    """
    path = Path(css_file_path)
    if not path.exists():
        raise FileNotFoundError(f"CSS file not found: {css_file_path}")

    content = path.read_text()
    pattern = re.compile(r"--([\w-]+)\s*:\s*([^;]+);")
    # Collapse internal whitespace so a multi-line declaration (a value wrapped
    # across lines keeps its newlines + indentation under `[^;]+`) reduces to a
    # single-spaced string coloraide can parse, rather than failing to resolve.
    return {name: " ".join(value.split()) for name, value in pattern.findall(content)}


def _expand_vars(raw: str, token_map: dict[str, str]) -> str:
    """Substitute every ``var(--x)`` reference in ``raw`` with its token value.

    Each iteration finds the first remaining ``var(--x)``, looks ``x`` up in
    ``token_map``, and replaces *all* occurrences of that exact variable in one
    pass. Repeating resolves nested references, where one token's value is
    itself a ``var()``.

    Example — a nested chain ``brand -> accent -> hex``::

        raw = "var(--brand)"
        token_map = {"brand": "var(--accent)", "accent": "#F59E0B"}

        # pass 1: expand --brand   -> "var(--accent)"
        # pass 2: expand --accent  -> "#F59E0B"
        # pass 3: no var() left    -> returned "#F59E0B"

    ``seen`` tracks which keys have already been expanded so a true cycle
    terminates instead of looping forever. A key encountered a second time means
    its own expansion (directly or transitively) reintroduced it — e.g.
    ``a -> var(--b)``, ``b -> var(--a)`` — and raises. ``seen`` is keyed per
    variable, not per occurrence: the *same* variable used in several sibling
    positions, like ``var(--color-primary), var(--color-primary) 12%``, is
    replaced together in that key's single pass, so it is never a cycle.

    Raises ColorResolveError on an unknown variable, a reference cycle, or a
    chain deeper than ``_MAX_VAR_DEPTH``.
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
        # Re-encountering a key already expanded means its replacement (directly
        # or transitively) re-introduced it — a genuine reference cycle. The
        # same variable legitimately used in several sibling positions is not a
        # cycle, so all of its occurrences are substituted in one pass below.
        if key in seen:
            raise ColorResolveError(
                f"Cyclic CSS variable reference involving {full_prop!r}"
            )
        seen.add(key)
        replacement = token_map[key]
        occurrence = re.compile(r"var\(\s*" + re.escape(full_prop) + r"\s*\)")
        current = occurrence.sub(replacement, current)
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


def _srgb_hex(color: Color) -> str:
    """Serialise a coloraide Color to an opaque 6-digit ``#rrggbb`` string.

    Email clients do not reliably support 8-digit ``#rrggbbaa`` hex, so a
    semi-transparent result is treated as a resolution failure (the caller
    warns and uses an opaque hex fallback) rather than emitted into email CSS.
    """
    result = color.convert("srgb").to_string(hex=True)
    if len(result) != 7:
        raise ColorResolveError(
            f"Resolved colour {result!r} is not an opaque #rrggbb value"
        )
    return result


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

    # Recursively resolve each colour operand (handles var() and nested
    # color-mix); resolve_css_color expands var() references itself.
    a_resolved = resolve_css_color(a_str, token_map)
    b_resolved = resolve_css_color(b_str, token_map)

    # Compute coloraide's mix weight (B's weight in the blend).
    # CSS color-mix rule: if both percentages are given they are normalised to
    # sum to 100 (so `A 20%, B 60%` is treated as 25/75). If only one p is given,
    # A gets p and B gets 100-p. If neither, 50/50. coloraide mix(b, weight=w)
    # takes B's weight.
    #
    # Intentional simplification: when both percentages are given and sum to less
    # than 100%, the CSS spec turns the shortfall into transparency. We renormalise
    # to full opacity instead — an opaque result is required anyway (a translucent
    # mix is rejected by _srgb_hex), and the theme tokens only ever use the
    # single-percentage form (`var(--primary), white 12%`), never two percentages.
    if a_pct is not None and b_pct is not None:
        total = a_pct + b_pct
        if total == 0:
            raise ColorResolveError(f"color-mix percentages sum to zero in {value!r}")
        b_weight = b_pct / total
    elif a_pct is not None:
        b_weight = (100.0 - a_pct) / 100.0
    elif b_pct is not None:
        b_weight = b_pct / 100.0
    else:
        b_weight = 0.5

    try:
        mixed = Color(a_resolved).mix(b_resolved, b_weight, space=space, powerless=True)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ColorResolveError(
            f"color-mix conversion failed for {value!r}: {exc}"
        ) from exc
    return _srgb_hex(mixed)


def resolve_css_color(raw: str, token_map: dict[str, str]) -> str:
    """Resolve a raw CSS color value to a 6-digit #rrggbb hex string.

    Handles hex (3/4/6/8-digit), rgb/rgba, hsl/hsla, oklch, oklab, lch, lab,
    named colors, var() references, and color-mix() expressions. var() is
    expanded first (see _expand_vars), then a color-mix() wrapper is resolved by
    blending its operands; anything else is parsed directly. An 8-digit hex has
    its alpha dropped to srgb, and a non-opaque result is rejected.

    Examples::

        resolve_css_color("#2B6CB0", {})  # -> "#2b6cb0"
        resolve_css_color("rgb(43, 108, 176)", {})  # -> "#2b6cb0"
        resolve_css_color("var(--brand)", {"brand": "white"})  # -> "#ffffff"
        resolve_css_color(
            "color-mix(in oklch, #ff0000 30%, #0000ff)", {}
        )  # -> a blended #rrggbb

    Raises ColorResolveError on any parse, cycle, or conversion failure.
    """
    resolved = _expand_vars(raw.strip(), token_map).strip()

    if resolved.startswith("color-mix("):
        return _resolve_color_mix(resolved, token_map)

    try:
        color = Color(resolved)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ColorResolveError(
            f"Cannot convert {resolved!r} (from {raw!r}) to hex: {exc}"
        ) from exc
    return _srgb_hex(color)


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

    The result is rendered with ``|safe`` in base_email.html (so the quotes
    around multi-word names survive premailer's CSS parsing). That is only
    safe because every emitted name comes from the fixed allowlist or the
    fixed generic families — keep this output allowlist-constrained, never
    pass arbitrary token text through.
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


def extract_font_family(token_map: dict[str, str]) -> str:
    """Extract an email-safe font-family stack from the theme token map.

    Returns ``email_safe_font_stack(token_map["fls-font-sans"])``. Raises
    EmailThemeError when ``--fls-font-sans`` is absent: the default theme always
    defines it, so absence even from the merged map is a misconfiguration.
    """
    raw = token_map.get("fls-font-sans")
    if raw is None:
        raise EmailThemeError("Theme token --fls-font-sans not found")
    return email_safe_font_stack(raw)


def extract_button_radius(token_map: dict[str, str]) -> str:
    """Extract the button border-radius value from the theme token map.

    Returns the value of ``--fls-radius-md`` (e.g. ``'0.375rem'``, ``'0.5rem'``,
    ``'6px'``) when it is a bare CSS length literal. Raises EmailThemeError when
    the token is absent or its value is not a plain length (a non-length value
    could inject CSS into the email <style> block).
    """
    raw = token_map.get("fls-radius-md")
    if raw is None:
        raise EmailThemeError("Theme token --fls-radius-md not found")
    raw = raw.strip()
    if not _LENGTH_RE.match(raw):
        raise EmailThemeError(
            f"Theme token --fls-radius-md={raw!r} is not a CSS length"
        )
    return raw


def resolved_email_logo_path() -> str | None:
    """Return the static path to use for the email logo.

    Checks EMAIL_LOGO_STATIC_PATH first, then falls back to HEADER_LOGO_STATIC_PATH.
    Returns None if neither is set.
    """
    from django.conf import settings

    return settings.EMAIL_LOGO_STATIC_PATH or settings.HEADER_LOGO_STATIC_PATH or None


def resolve_color_token(token_map: dict[str, str], token: str) -> str:
    """Resolve ``color-<token>`` from the token map to a #rrggbb hex string.

    Raises ColorResolveError if the token is absent from the map or its raw
    value cannot be resolved. There is no fallback: get_email_theme merges the
    default theme under the active theme, so the default theme is the single
    source of default values and a token unresolvable even there is a genuine
    misconfiguration that should fail loud rather than render a wrong colour.
    """
    raw = token_map.get(f"color-{token}")
    if raw is None:
        raise ColorResolveError(f"Email colour token --color-{token} not found")
    try:
        return resolve_css_color(raw, token_map)
    except (ColorResolveError, ValueError) as exc:
        raise ColorResolveError(
            f"Email colour token --color-{token}={raw!r} could not be resolved: {exc}"
        ) from exc


def default_theme_css_path() -> str:
    """Return the filesystem path to the *default* theme's ``theme.css``.

    The default theme ships with FLS and is the single source of default email
    token values. Resolved through ``FLS_THEMES_DIRS`` so a downstream project
    that shadows ``default/`` is honoured.
    """
    from django.conf import settings

    from freedom_ls.base.theming import resolve_theme_dir

    resolved = resolve_theme_dir(DEFAULT_THEME_SLUG, settings.FLS_THEMES_DIRS)
    return str(resolved / "static" / "themes" / DEFAULT_THEME_SLUG / "theme.css")


def active_theme_css_path() -> str:
    """Return the filesystem path to the active theme's ``theme.css``.

    Built from the genuine settings (``RESOLVED_THEME_DIR`` and ``FLS_THEME``)
    rather than stored as a setting itself — it is a derived path. Pairs with
    ``default_theme_css_path``; ``get_email_theme`` merges the two.
    """
    from django.conf import settings

    return str(
        Path(settings.RESOLVED_THEME_DIR)
        / "static"
        / "themes"
        / settings.FLS_THEME
        / "theme.css"
    )


@dataclass(frozen=True)
class EmailTheme:
    """Resolved, email-safe theme values consumed by the email templates.

    The Python field names form the email-template contract; the colour role a
    field maps to is noted where the two differ (``foreground`` ← ``on-surface``).
    """

    color_primary: str
    color_on_primary: str
    color_foreground: str  # role: on-surface
    color_muted: str
    color_surface: str
    color_surface_2: str
    color_border: str
    color_header: str
    color_on_header: str
    font_family: str
    button_radius: str


@functools.cache
def get_email_theme() -> EmailTheme:
    """Resolve the active theme's email colours, font, and button radius.

    The default theme's ``theme.css`` provides the baseline token values; the
    active theme's tokens are layered on top (active wins per-token), so any
    token the active theme omits falls through to the default. Lazily derived
    and cached for the process lifetime (so a future bulk send resolves it
    once). Tests that override the theme must call ``get_email_theme.cache_clear()``.

    Raises EmailThemeError (incl. ColorResolveError) if a required token cannot
    be resolved even from the default theme — a genuine misconfiguration that
    fails loud rather than silently rendering a wrong colour.
    """
    default_map = parse_tailwind_tokens(default_theme_css_path())
    try:
        active_map = parse_tailwind_tokens(active_theme_css_path())
    except FileNotFoundError:
        # A sparse/Tier-1 active theme may ship no theme.css of its own; the
        # default baseline below still supplies every token.
        active_map = {}
    token_map = {**default_map, **active_map}

    colors = {
        field: resolve_color_token(token_map, role) for role, field in EMAIL_COLOR_ROLES
    }
    return EmailTheme(
        **colors,
        font_family=extract_font_family(token_map),
        button_radius=extract_button_radius(token_map),
    )


def image_dimensions(path: str) -> tuple[int, int] | None:
    """Return the intrinsic ``(width, height)`` in pixels of an image file.

    Parses the header of PNG, GIF, and JPEG files using only the stdlib. Returns
    None for an unreadable file or an unrecognised/unsupported format.
    """
    try:
        with open(path, "rb") as fh:
            head = fh.read(26)
            if len(head) >= 24 and head[:8] == b"\x89PNG\r\n\x1a\n":
                # IHDR width/height are the two big-endian uint32 at offset 16.
                width, height = struct.unpack(">II", head[16:24])
                return int(width), int(height)
            if len(head) >= 10 and head[:6] in (b"GIF87a", b"GIF89a"):
                # Logical screen width/height: little-endian uint16 at offset 6.
                width, height = struct.unpack("<HH", head[6:10])
                return int(width), int(height)
            if len(head) >= 2 and head[:2] == b"\xff\xd8":
                return _jpeg_dimensions(fh)
    except OSError:
        return None
    return None


def _jpeg_dimensions(fh: BinaryIO) -> tuple[int, int] | None:
    """Read ``(width, height)`` from a JPEG's first SOF marker, or None."""
    fh.seek(2)
    while True:
        byte = fh.read(1)
        if not byte:
            return None
        if byte != b"\xff":
            continue
        marker = fh.read(1)
        while marker == b"\xff":  # skip fill bytes
            marker = fh.read(1)
        if not marker:
            return None
        # SOF0..SOF15 carry the frame dimensions; C4/C8/CC are not SOF markers.
        if marker[0] in {*range(0xC0, 0xD0)} - {0xC4, 0xC8, 0xCC}:
            fh.read(3)  # segment length (2) + sample precision (1)
            data = fh.read(4)
            if len(data) < 4:
                return None
            height, width = struct.unpack(">HH", data)
            return int(width), int(height)
        seg_len = fh.read(2)
        if len(seg_len) < 2:
            return None
        fh.seek(struct.unpack(">H", seg_len)[0] - 2, 1)


@functools.cache
def email_logo_dimensions(logo_static_path: str) -> tuple[int, int] | None:
    """Return the ``(width, height)`` to render the email logo at, or None.

    Locates the source static file, reads its intrinsic size, and scales it to
    ``EMAIL_LOGO_DISPLAY_HEIGHT`` so the aspect ratio is preserved. Returns None
    when the file cannot be located or its dimensions cannot be read (the
    template then falls back to a height-only constraint). Cached for the
    process lifetime.
    """
    from django.contrib.staticfiles import finders

    absolute_path = finders.find(logo_static_path)
    if absolute_path is None:
        return None

    intrinsic = image_dimensions(absolute_path)
    if intrinsic is None:
        return None

    intrinsic_width, intrinsic_height = intrinsic
    if intrinsic_height <= 0 or intrinsic_width <= 0:
        return None

    height = EMAIL_LOGO_DISPLAY_HEIGHT
    width = round(intrinsic_width * height / intrinsic_height)
    return width, height
