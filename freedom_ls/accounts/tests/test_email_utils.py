import warnings
from pathlib import Path
from unittest.mock import patch

import pytest

from freedom_ls.accounts.email_utils import (
    EMAIL_LOGO_DISPLAY_HEIGHT,
    ColorResolveError,
    EmailThemeError,
    email_logo_dimensions,
    email_safe_font_stack,
    extract_button_radius,
    extract_font_family,
    get_email_theme,
    image_dimensions,
    parse_tailwind_tokens,
    resolve_color_token,
    resolve_css_color,
)

# ---------------------------------------------------------------------------
# parse_tailwind_tokens — Task 1.1
# ---------------------------------------------------------------------------


def test_parse_tailwind_tokens_returns_all_custom_properties(make_temp_file):
    """All --<name> tokens are returned keyed by full-name-minus-leading-dashes."""
    css_content = """
@theme {
    --color-primary: #2B6CB0;
    --fls-radius-md: 0.375rem;
    --fls-font-sans: Arial, sans-serif;
    --font-size-base: 16px;
}
"""
    css_file = make_temp_file(".css", css_content)
    result = parse_tailwind_tokens(str(css_file))

    assert result["color-primary"] == "#2B6CB0"
    assert result["fls-radius-md"] == "0.375rem"
    assert result["fls-font-sans"] == "Arial, sans-serif"
    assert result["font-size-base"] == "16px"


def test_parse_tailwind_tokens_captures_non_hex_color_values(make_temp_file):
    """Non-hex color values (rgb, hsl, oklch, color-mix, var, named) are captured raw."""
    css_content = """
@theme {
    --color-a: rgb(255, 0, 0);
    --color-b: hsl(120, 100%, 50%);
    --color-c: oklch(70% 0.15 180);
    --color-d: color-mix(in oklch, #ff0000 30%, #0000ff);
    --color-e: var(--color-a);
    --color-f: white;
}
"""
    css_file = make_temp_file(".css", css_content)
    result = parse_tailwind_tokens(str(css_file))

    assert result["color-a"] == "rgb(255, 0, 0)"
    assert result["color-b"] == "hsl(120, 100%, 50%)"
    assert result["color-c"] == "oklch(70% 0.15 180)"
    assert result["color-d"] == "color-mix(in oklch, #ff0000 30%, #0000ff)"
    assert result["color-e"] == "var(--color-a)"
    assert result["color-f"] == "white"


def test_parse_tailwind_tokens_missing_file_raises():
    """Missing file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="CSS file not found"):
        parse_tailwind_tokens("/nonexistent/path/to/file.css")


def test_parse_tailwind_tokens_does_not_include_non_custom_properties(make_temp_file):
    """Standard (non-custom) properties are not included in the token map."""
    css_content = """
@theme {
    --color-primary: #2B6CB0;
    color: red;
    background: white;
}
"""
    css_file = make_temp_file(".css", css_content)
    result = parse_tailwind_tokens(str(css_file))

    assert "color-primary" in result
    assert "color" not in result
    assert "background" not in result


def test_parse_tailwind_tokens_collapses_multiline_value_whitespace(make_temp_file):
    """A value wrapped across lines collapses to a single-spaced string."""
    css_content = """
@theme {
    --fls-font-sans: ui-sans-serif,
        "Helvetica Neue",
        Arial,
        sans-serif;
}
"""
    css_file = make_temp_file(".css", css_content)
    result = parse_tailwind_tokens(str(css_file))

    assert result["fls-font-sans"] == (
        'ui-sans-serif, "Helvetica Neue", Arial, sans-serif'
    )


# ---------------------------------------------------------------------------
# resolve_css_color — Task 1.2
# ---------------------------------------------------------------------------

HEX_PATTERN = r"^#[0-9a-fA-F]{6}$"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Exact round-trips: hex formats
        ("#2B6CB0", "#2b6cb0"),
        ("#fff", "#ffffff"),
        ("#FFAA00FF", "#ffaa00"),  # 8-digit hex, alpha dropped to srgb
        ("#123", "#112233"),  # 3-digit expands
        # Exact round-trips: named colors
        ("red", "#ff0000"),
        ("white", "#ffffff"),
        ("black", "#000000"),
        # rgb/rgba — exact
        ("rgb(43, 108, 176)", "#2b6cb0"),
        ("rgba(43, 108, 176, 1)", "#2b6cb0"),
        # These formats are validated by format-only (expected=None): just #rrggbb
        ("hsl(210, 60%, 43%)", None),
        ("oklch(50% 0.15 240)", None),
        ("oklab(0.5 0 -0.1)", None),
    ],
)
def test_resolve_css_color_returns_hex(raw, expected):
    """Various color formats resolve to 6-digit #rrggbb."""
    import re

    result = resolve_css_color(raw, {})
    assert re.match(r"^#[0-9a-f]{6}$", result), f"{raw!r} -> {result!r} is not #rrggbb"
    if expected is not None:
        assert result == expected


def test_resolve_css_color_var_two_pass_resolution():
    """var(--x) references are substituted from the token map."""
    token_map = {
        "color-primary": "#2B6CB0",
        "color-alias": "var(--color-primary)",
    }
    result = resolve_css_color("var(--color-alias)", token_map)
    assert result == "#2b6cb0"


def test_resolve_css_color_unknown_var_raises():
    """A var() pointing to a missing token raises ColorResolveError."""
    with pytest.raises(ColorResolveError):
        resolve_css_color("var(--color-nonexistent)", {})


def test_resolve_css_color_cyclic_var_raises_not_infinite_loop():
    """A cyclic var() chain raises ColorResolveError without hanging."""
    token_map = {
        "color-a": "var(--color-b)",
        "color-b": "var(--color-a)",
    }
    with pytest.raises(ColorResolveError):
        resolve_css_color("var(--color-a)", token_map)


def test_resolve_css_color_mix_returns_intermediate_hex():
    """color-mix(in oklch, A p%, B) returns a hex value between A and B."""
    import re

    result = resolve_css_color("color-mix(in oklch, #ff0000 30%, #0000ff)", {})
    assert re.match(r"^#[0-9a-f]{6}$", result)
    # The result must differ from both endpoints
    assert result != "#ff0000"
    assert result != "#0000ff"


def test_resolve_css_color_same_var_used_twice_is_not_a_cycle():
    """The same var() in two sibling positions resolves; it is not a cycle."""
    import re

    token_map = {"color-primary": "#2B6CB0"}
    raw = "color-mix(in oklch, var(--color-primary), var(--color-primary) 12%)"
    result = resolve_css_color(raw, token_map)
    assert re.match(r"^#[0-9a-f]{6}$", result)


def test_resolve_css_color_mix_with_var_references():
    """color-mix resolves var() references within its arguments."""
    import re

    token_map = {
        "color-primary": "#2B6CB0",
        "fls-hover-mix-color": "white",
        "fls-hover-mix-amount": "12%",
    }
    raw = "color-mix(in oklch, var(--color-primary), var(--fls-hover-mix-color) 12%)"
    result = resolve_css_color(raw, token_map)
    assert re.match(r"^#[0-9a-f]{6}$", result)
    assert result != "#2b6cb0"
    assert result != "#ffffff"


def test_resolve_css_color_mix_both_percentages_are_normalised():
    """Two percentages that don't sum to 100 are normalised (20/60 == 25/75)."""
    unnormalised = resolve_css_color("color-mix(in srgb, #000000 20%, #ffffff 60%)", {})
    normalised = resolve_css_color("color-mix(in srgb, #000000 25%, #ffffff 75%)", {})
    assert unnormalised == normalised


def test_resolve_css_color_mix_both_percentages_zero_raises():
    """Two zero percentages have no valid normalisation and raise."""
    with pytest.raises(ColorResolveError):
        resolve_css_color("color-mix(in srgb, #000000 0%, #ffffff 0%)", {})


# ---------------------------------------------------------------------------
# resolve_color_token — Task 1.3
# ---------------------------------------------------------------------------


def test_resolve_color_token_missing_token_raises():
    """A missing --color-<token> raises ColorResolveError (no silent fallback)."""
    token_map: dict[str, str] = {}
    with pytest.raises(ColorResolveError, match="--color-primary not found"):
        resolve_color_token(token_map, "primary")


def test_resolve_color_token_unparseable_value_raises():
    """An unparseable raw value raises ColorResolveError."""
    token_map = {"color-primary": "not-a-real-color-value!!##"}
    with pytest.raises(ColorResolveError):
        resolve_color_token(token_map, "primary")


def test_resolve_color_token_cyclic_var_raises():
    """A cyclic var() chain raises ColorResolveError rather than looping."""
    token_map = {"color-primary": "var(--color-primary)"}
    with pytest.raises(ColorResolveError, match="--color-primary"):
        resolve_color_token(token_map, "primary")


def test_resolve_color_token_valid_hex_returns_resolved_hex():
    """A valid hex token returns the resolved #rrggbb string."""
    token_map = {"color-primary": "#2B6CB0"}
    result = resolve_color_token(token_map, "primary")
    assert result == "#2b6cb0"


# ---------------------------------------------------------------------------
# Back-compat oracle — Task 1.3
# Real theme files resolve to known hex values
# ---------------------------------------------------------------------------

_THEMES_BASE = Path(__file__).resolve().parents[3] / "freedom_ls" / "themes"


def _make_token_map(theme_name: str) -> dict[str, str]:
    css_path = (
        _THEMES_BASE / theme_name / "static" / "themes" / theme_name / "theme.css"
    )
    return parse_tailwind_tokens(str(css_path))


def test_default_theme_email_colors_resolve_to_expected_hex():
    """default theme: seven email colour tokens resolve to their known hex values."""
    token_map = _make_token_map("default")
    assert resolve_color_token(token_map, "primary") == "#2b6cb0"
    assert resolve_color_token(token_map, "on-surface") == "#1a2332"
    assert resolve_color_token(token_map, "muted") == "#4a5568"
    assert resolve_color_token(token_map, "surface") == "#ffffff"
    assert resolve_color_token(token_map, "surface-2") == "#f3f4f6"
    assert resolve_color_token(token_map, "on-primary") == "#ffffff"
    assert resolve_color_token(token_map, "border") == "#d1d5db"


def test_first_class_theme_email_colors_resolve_to_expected_hex():
    """first_class theme: seven email colour tokens resolve to their known hex values."""
    token_map = _make_token_map("first_class")
    assert resolve_color_token(token_map, "primary") == "#283593"
    assert resolve_color_token(token_map, "on-surface") == "#1a1a2e"
    assert resolve_color_token(token_map, "muted") == "#718096"
    assert resolve_color_token(token_map, "surface") == "#f8f9fc"
    assert resolve_color_token(token_map, "surface-2") == "#edf2f7"
    assert resolve_color_token(token_map, "on-primary") == "#ffffff"
    assert resolve_color_token(token_map, "border") == "#e2e8f0"


# ---------------------------------------------------------------------------
# email_safe_font_stack — Task 2.2
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Mixed stack: keywords + custom + allowlisted + generic
        # ui-sans-serif, system-ui, -apple-system dropped; Segoe UI, Roboto, Noto Sans dropped;
        # "Helvetica Neue" and Arial kept; sans-serif kept as generic.
        (
            'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif',
            '"Helvetica Neue", Arial, sans-serif',
        ),
        # Custom-only: DM Sans is not on the allowlist, system-ui is a keyword;
        # only sans-serif generic remains (+ warning emitted separately).
        ('"DM Sans", system-ui, sans-serif', "sans-serif"),
        # Single allowlisted name with generic
        ("Arial, sans-serif", "Arial, sans-serif"),
        # Multi-word allowlisted name is re-quoted
        ("Helvetica Neue, sans-serif", '"Helvetica Neue", sans-serif'),
        # Already-quoted multi-word allowlisted name preserved
        ('"Helvetica Neue", sans-serif', '"Helvetica Neue", sans-serif'),
        # No generic present: one is appended
        ("Arial, Helvetica", "Arial, Helvetica, sans-serif"),
        # All keywords, no generics: sans-serif appended
        ("system-ui, ui-sans-serif, -apple-system", "sans-serif"),
        # Serif generic kept
        ("Georgia, serif", "Georgia, serif"),
        # Monospace generic kept
        ('"Courier New", monospace', '"Courier New", monospace'),
        # Other ui-* keywords dropped
        ("ui-monospace, monospace", "monospace"),
        # Case-insensitive allowlist match
        ("ARIAL, sans-serif", "ARIAL, sans-serif"),
        # Tahoma is on the allowlist
        ("Tahoma, sans-serif", "Tahoma, sans-serif"),
        # Trebuchet MS is on the allowlist; multi-word gets quoted
        ("Trebuchet MS, sans-serif", '"Trebuchet MS", sans-serif'),
        # Verdana is on the allowlist
        ("Verdana, sans-serif", "Verdana, sans-serif"),
        # Times New Roman is on the allowlist; multi-word gets quoted
        ("Times New Roman, serif", '"Times New Roman", serif'),
    ],
)
def test_email_safe_font_stack_returns_expected_stack(raw: str, expected: str) -> None:
    """email_safe_font_stack filters the CSS font stack to email-safe names."""
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        result = email_safe_font_stack(raw)
    assert result == expected


def test_email_safe_font_stack_custom_only_emits_warning() -> None:
    """A stack reduced to only the generic emits a UserWarning about custom fonts."""
    with pytest.warns(UserWarning, match="email-safe allowlist"):
        email_safe_font_stack('"DM Sans", system-ui, sans-serif')


def test_email_safe_font_stack_default_theme_produces_documented_stack() -> None:
    """default theme fls-font-sans produces the documented email font stack."""
    token_map = _make_token_map("default")
    raw = token_map["fls-font-sans"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        result = email_safe_font_stack(raw)
    assert result == '"Helvetica Neue", Arial, sans-serif'


def test_email_safe_font_stack_first_class_theme_produces_documented_stack() -> None:
    """first_class theme fls-font-sans produces the documented email font stack (+ warning)."""
    token_map = _make_token_map("first_class")
    raw = token_map["fls-font-sans"]
    with pytest.warns(UserWarning, match="email-safe allowlist"):
        result = email_safe_font_stack(raw)
    assert result == "sans-serif"


# ---------------------------------------------------------------------------
# extract_font_family — Task 2.2 (settings-level derivation)
# ---------------------------------------------------------------------------


def test_extract_font_family_missing_token_raises() -> None:
    """When fls-font-sans is absent, EmailThemeError is raised (no silent fallback)."""
    token_map: dict[str, str] = {}
    with pytest.raises(EmailThemeError, match="--fls-font-sans not found"):
        extract_font_family(token_map)


def test_extract_font_family_present_token_delegates_to_email_safe_font_stack() -> None:
    """When fls-font-sans is present, the email-safe stack is returned."""
    token_map = {"fls-font-sans": "Arial, sans-serif"}
    result = extract_font_family(token_map)
    assert result == "Arial, sans-serif"


# ---------------------------------------------------------------------------
# extract_button_radius — Task 2.3
# ---------------------------------------------------------------------------


def test_extract_button_radius_present_token_returns_value() -> None:
    """When fls-radius-md is in the token map, its value is returned as-is."""
    token_map = {"fls-radius-md": "0.5rem"}
    result = extract_button_radius(token_map)
    assert result == "0.5rem"


def test_extract_button_radius_missing_token_raises() -> None:
    """When fls-radius-md is absent, EmailThemeError is raised (no silent fallback)."""
    token_map: dict[str, str] = {}
    with pytest.raises(EmailThemeError, match="--fls-radius-md not found"):
        extract_button_radius(token_map)


@pytest.mark.parametrize(
    "raw",
    [
        "6px",
        "0.375rem",
        "0.5em",
        "0",
        "50%",
        "  8px  ",
    ],
)
def test_extract_button_radius_accepts_length_literals(raw: str) -> None:
    """Bare CSS length literals are returned (stripped)."""
    token_map = {"fls-radius-md": raw}
    result = extract_button_radius(token_map)
    assert result == raw.strip()


@pytest.mark.parametrize(
    "raw",
    [
        "0} body{display:none",
        "6px; color: red",
        "calc(1rem + 2px)",
        "red",
        "6",
        "",
    ],
)
def test_extract_button_radius_rejects_non_length_and_raises(raw: str) -> None:
    """A value that is not a plain length raises (no CSS injection, no fallback)."""
    token_map = {"fls-radius-md": raw}
    with pytest.raises(EmailThemeError, match="is not a CSS length"):
        extract_button_radius(token_map)


def test_extract_button_radius_default_theme_yields_expected_value() -> None:
    """default theme fls-radius-md resolves to '0.375rem'."""
    token_map = _make_token_map("default")
    result = extract_button_radius(token_map)
    assert result == "0.375rem"


def test_extract_button_radius_first_class_theme_yields_expected_value() -> None:
    """first_class theme fls-radius-md resolves to '0.5rem'."""
    token_map = _make_token_map("first_class")
    result = extract_button_radius(token_map)
    assert result == "0.5rem"


# ---------------------------------------------------------------------------
# Header role tokens
# ---------------------------------------------------------------------------


def test_default_theme_header_tokens_resolve_to_primary() -> None:
    """default theme: header aliases primary, on-header aliases on-primary."""
    token_map = _make_token_map("default")
    assert resolve_color_token(token_map, "header") == "#2b6cb0"
    assert resolve_color_token(token_map, "on-header") == "#ffffff"


def test_first_class_theme_header_is_white_with_dark_on_header() -> None:
    """first_class theme: header is white, on-header is the dark on-surface colour."""
    token_map = _make_token_map("first_class")
    assert resolve_color_token(token_map, "header") == "#ffffff"
    # on-header -> var(--color-on-surface); just assert it is not white.
    assert resolve_color_token(token_map, "on-header") != "#ffffff"


# ---------------------------------------------------------------------------
# image_dimensions / email_logo_dimensions
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LOGO_STATIC_PATH = "images/first_class_logo.png"
_LOGO_FILE = _REPO_ROOT / "static" / "images" / "first_class_logo.png"


def test_image_dimensions_reads_png_intrinsic_size() -> None:
    """The bundled PNG logo reports its real 512x248 pixel size."""
    assert image_dimensions(str(_LOGO_FILE)) == (512, 248)


def test_image_dimensions_returns_none_for_non_image(make_temp_file) -> None:
    """A non-image file yields None rather than raising."""
    not_an_image = make_temp_file(".css", "--color-primary: #2B6CB0;")
    assert image_dimensions(str(not_an_image)) is None


def test_image_dimensions_returns_none_for_missing_file(tmp_path) -> None:
    """A path that does not exist yields None."""
    assert image_dimensions(str(tmp_path / "nope.png")) is None


def test_email_logo_dimensions_scales_to_display_height() -> None:
    """The logo is scaled to the fixed display height with width preserving ratio."""
    email_logo_dimensions.cache_clear()
    try:
        result = email_logo_dimensions(_LOGO_STATIC_PATH)
    finally:
        email_logo_dimensions.cache_clear()
    # 512x248 scaled to height 48 -> width round(512*48/248) = 99.
    assert result == (99, EMAIL_LOGO_DISPLAY_HEIGHT)


def test_email_logo_dimensions_returns_none_for_unfound_static() -> None:
    """An unresolvable static path yields None (template falls back to height-only)."""
    email_logo_dimensions.cache_clear()
    try:
        assert email_logo_dimensions("images/does_not_exist_logo.png") is None
    finally:
        email_logo_dimensions.cache_clear()


# ---------------------------------------------------------------------------
# get_email_theme
# ---------------------------------------------------------------------------


def test_get_email_theme_resolves_active_default_theme() -> None:
    """Under the (test default) theme, header mirrors primary and on-header is white."""
    get_email_theme.cache_clear()
    try:
        theme = get_email_theme()
    finally:
        get_email_theme.cache_clear()
    assert theme.color_primary == "#2b6cb0"
    assert theme.color_header == "#2b6cb0"
    assert theme.color_on_header == "#ffffff"
    assert theme.color_foreground == "#1a2332"


def test_get_email_theme_falls_back_to_default_theme_when_active_css_missing(
    tmp_path,
) -> None:
    """A missing *active* theme.css falls through to the default theme's values."""
    absent = str(tmp_path / "nope" / "theme.css")
    get_email_theme.cache_clear()
    try:
        with patch(
            "freedom_ls.accounts.email_utils.active_theme_css_path",
            return_value=absent,
        ):
            theme = get_email_theme()
    finally:
        get_email_theme.cache_clear()
    # Resolved from the real default theme.css (not a hardcoded copy), so the
    # values are the default theme's, lowercased by the colour resolver.
    assert theme.color_primary == "#2b6cb0"
    assert theme.color_header == "#2b6cb0"
    assert theme.button_radius == "0.375rem"


def test_get_email_theme_raises_when_default_theme_css_missing(tmp_path) -> None:
    """A missing *default* theme.css fails loud rather than rendering wrong colours."""
    absent = str(tmp_path / "nope" / "theme.css")
    get_email_theme.cache_clear()
    try:
        with (
            patch(
                "freedom_ls.accounts.email_utils.default_theme_css_path",
                return_value=absent,
            ),
            pytest.raises(FileNotFoundError),
        ):
            get_email_theme()
    finally:
        get_email_theme.cache_clear()
