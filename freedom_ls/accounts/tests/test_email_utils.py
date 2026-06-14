import warnings
from pathlib import Path

import pytest

from freedom_ls.accounts.email_utils import (
    ColorResolveError,
    email_safe_font_stack,
    extract_button_radius,
    extract_font_family,
    parse_tailwind_colors,
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


# ---------------------------------------------------------------------------
# parse_tailwind_colors — Task 1.1 (back-compat wrapper)
# ---------------------------------------------------------------------------


def test_parse_tailwind_colors_from_css_file(make_temp_file):
    """Test parsing --color-* custom properties from a CSS file."""
    css_content = """
@theme {
    --color-primary: #2B6CB0;
    --color-foreground: #1A2332;
    --color-muted: #4A5568;
}
"""
    css_file = make_temp_file(".css", css_content)
    result = parse_tailwind_colors(str(css_file))

    assert result == {
        "primary": "#2B6CB0",
        "foreground": "#1A2332",
        "muted": "#4A5568",
    }


def test_parse_tailwind_colors_missing_file_raises():
    """Test that a missing file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="CSS file not found"):
        parse_tailwind_colors("/nonexistent/path/to/file.css")


def test_parse_tailwind_colors_only_captures_color_properties(make_temp_file):
    """Test that only --color-* properties are parsed, not other custom properties."""
    css_content = """
@theme {
    --color-primary: #2B6CB0;
    --fls-font-sans: Arial, sans-serif;
    --fls-radius-md: 0.375rem;
    --color-success: #38A169;
}
"""
    css_file = make_temp_file(".css", css_content)
    result = parse_tailwind_colors(str(css_file))

    assert result == {
        "primary": "#2B6CB0",
        "success": "#38A169",
    }
    assert "fls-font-sans" not in result
    assert "fls-radius-md" not in result


def test_parse_tailwind_colors_handles_hyphenated_names(make_temp_file):
    """Test that hyphenated color names like primary-bold are parsed correctly."""
    css_content = """
@theme {
    --color-primary: #2B6CB0;
    --color-primary-bold: #1A4B8C;
    --color-success-bold: #276749;
}
"""
    css_file = make_temp_file(".css", css_content)
    result = parse_tailwind_colors(str(css_file))

    assert result == {
        "primary": "#2B6CB0",
        "primary-bold": "#1A4B8C",
        "success-bold": "#276749",
    }


def test_parse_tailwind_colors_now_captures_non_hex_values(make_temp_file):
    """Non-hex color values (rgb, named) are now captured as raw strings."""
    css_content = """
@theme {
    --color-primary: #2B6CB0;
    --color-text: rgb(0, 0, 0);
    --color-bg: white;
    --color-accent: #FF5733;
}
"""
    css_file = make_temp_file(".css", css_content)
    result = parse_tailwind_colors(str(css_file))

    assert result == {
        "primary": "#2B6CB0",
        "text": "rgb(0, 0, 0)",
        "bg": "white",
        "accent": "#FF5733",
    }


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


# ---------------------------------------------------------------------------
# resolve_color_token — Task 1.3
# ---------------------------------------------------------------------------


def test_resolve_color_token_missing_token_warns_and_returns_fallback():
    """Missing --color-<token> emits UserWarning and returns the fallback."""
    token_map: dict[str, str] = {}
    with pytest.warns(UserWarning, match="--color-primary not found"):
        result = resolve_color_token(token_map, "primary", "#2B6CB0")
    assert result == "#2B6CB0"


def test_resolve_color_token_unparseable_value_warns_and_returns_fallback():
    """An unparseable raw value emits UserWarning and returns the fallback."""
    token_map = {"color-primary": "not-a-real-color-value!!##"}
    with pytest.warns(UserWarning, match="could not be resolved"):
        result = resolve_color_token(token_map, "primary", "#2B6CB0")
    assert result == "#2B6CB0"


def test_resolve_color_token_cyclic_var_warns_and_returns_fallback():
    """A cyclic var() chain emits UserWarning and returns the fallback."""
    token_map = {
        "color-primary": "var(--color-primary)",
    }
    with pytest.warns(UserWarning, match="--color-primary"):
        result = resolve_color_token(token_map, "primary", "#2B6CB0")
    assert result == "#2B6CB0"


def test_resolve_color_token_valid_hex_returns_resolved_hex():
    """A valid hex token returns the resolved #rrggbb string."""
    token_map = {"color-primary": "#2B6CB0"}
    result = resolve_color_token(token_map, "primary", "#000000")
    assert result == "#2b6cb0"


def test_resolve_color_token_never_raises():
    """resolve_color_token never raises, even on bad input."""
    token_map = {"color-primary": "var(--color-a)", "color-a": "var(--color-primary)"}
    # Should not raise
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        result = resolve_color_token(token_map, "primary", "#123456")
    assert result == "#123456"


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
    assert resolve_color_token(token_map, "primary", "#000000") == "#2b6cb0"
    assert resolve_color_token(token_map, "on-surface", "#000000") == "#1a2332"
    assert resolve_color_token(token_map, "muted", "#000000") == "#4a5568"
    assert resolve_color_token(token_map, "surface", "#000000") == "#ffffff"
    assert resolve_color_token(token_map, "surface-2", "#000000") == "#f3f4f6"
    assert resolve_color_token(token_map, "on-primary", "#000000") == "#ffffff"
    assert resolve_color_token(token_map, "border", "#000000") == "#d1d5db"


def test_first_class_theme_email_colors_resolve_to_expected_hex():
    """first_class theme: seven email colour tokens resolve to their known hex values."""
    token_map = _make_token_map("first_class")
    assert resolve_color_token(token_map, "primary", "#000000") == "#283593"
    assert resolve_color_token(token_map, "on-surface", "#000000") == "#1a1a2e"
    assert resolve_color_token(token_map, "muted", "#000000") == "#718096"
    assert resolve_color_token(token_map, "surface", "#000000") == "#f8f9fc"
    assert resolve_color_token(token_map, "surface-2", "#000000") == "#edf2f7"
    assert resolve_color_token(token_map, "on-primary", "#000000") == "#ffffff"
    assert resolve_color_token(token_map, "border", "#000000") == "#e2e8f0"


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


def test_extract_font_family_missing_token_returns_fallback_and_warns() -> None:
    """When fls-font-sans is absent, the fallback is returned and a UserWarning is emitted."""
    token_map: dict[str, str] = {}
    with pytest.warns(UserWarning, match="--fls-font-sans not found"):
        result = extract_font_family(token_map, fallback="Arial, Helvetica, sans-serif")
    assert result == "Arial, Helvetica, sans-serif"


def test_extract_font_family_present_token_delegates_to_email_safe_font_stack() -> None:
    """When fls-font-sans is present, the email-safe stack is returned."""
    token_map = {"fls-font-sans": "Arial, sans-serif"}
    result = extract_font_family(token_map, fallback="fallback-value")
    assert result == "Arial, sans-serif"


# ---------------------------------------------------------------------------
# extract_button_radius — Task 2.3
# ---------------------------------------------------------------------------


def test_extract_button_radius_present_token_returns_value() -> None:
    """When fls-radius-md is in the token map, its value is returned as-is."""
    token_map = {"fls-radius-md": "0.5rem"}
    result = extract_button_radius(token_map, fallback="6px")
    assert result == "0.5rem"


def test_extract_button_radius_missing_token_returns_fallback_and_warns() -> None:
    """When fls-radius-md is absent, the fallback is returned and a UserWarning is emitted."""
    token_map: dict[str, str] = {}
    with pytest.warns(UserWarning, match="--fls-radius-md not found"):
        result = extract_button_radius(token_map, fallback="6px")
    assert result == "6px"


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
    result = extract_button_radius(token_map, fallback="6px")
    assert result == raw.strip()


@pytest.mark.parametrize(
    "raw",
    [
        "0} body{display:none",
        "6px; color: red",
        "calc(1rem + 2px)",
        "red",
        "",
    ],
)
def test_extract_button_radius_rejects_non_length_and_warns(raw: str) -> None:
    """A value that is not a plain length warns and falls back (no CSS injection)."""
    token_map = {"fls-radius-md": raw}
    with pytest.warns(UserWarning, match="is not a CSS length"):
        result = extract_button_radius(token_map, fallback="6px")
    assert result == "6px"


def test_extract_button_radius_default_theme_yields_expected_value() -> None:
    """default theme fls-radius-md resolves to '0.375rem'."""
    token_map = _make_token_map("default")
    result = extract_button_radius(token_map, fallback="6px")
    assert result == "0.375rem"


def test_extract_button_radius_first_class_theme_yields_expected_value() -> None:
    """first_class theme fls-radius-md resolves to '0.5rem'."""
    token_map = _make_token_map("first_class")
    result = extract_button_radius(token_map, fallback="6px")
    assert result == "0.5rem"
