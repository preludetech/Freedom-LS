import warnings
from pathlib import Path

import pytest

from freedom_ls.accounts.email_utils import (
    ColorResolveError,
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
