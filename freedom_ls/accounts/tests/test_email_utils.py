import pytest

from freedom_ls.accounts.email_utils import parse_tailwind_colors


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
    --font-size-base: 16px;
    --spacing-lg: 24px;
    --color-success: #38A169;
}
"""
    css_file = make_temp_file(".css", css_content)
    result = parse_tailwind_colors(str(css_file))

    assert result == {
        "primary": "#2B6CB0",
        "success": "#38A169",
    }


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


def test_parse_tailwind_colors_handles_new_role_names(make_temp_file):
    """The post-Phase-1 role surface (`on-surface`, `error`, `info`, `secondary`,
    `accent`, `on-success`, `on-error`, …) is parsed without special handling —
    `parse_tailwind_colors` is generic over `--color-<name>` patterns.
    """
    css_content = """
@theme {
    --color-primary: #2B6CB0;
    --color-on-primary: #FFFFFF;
    --color-secondary: #475569;
    --color-on-secondary: #FFFFFF;
    --color-accent: #F59E0B;
    --color-on-accent: #1A2332;
    --color-success: #38A169;
    --color-on-success: #FFFFFF;
    --color-warning: #F6E05E;
    --color-on-warning: #1A2332;
    --color-error: #E8553D;
    --color-on-error: #FFFFFF;
    --color-info: #0EA5E9;
    --color-on-info: #FFFFFF;
    --color-surface: #FFFFFF;
    --color-surface-2: #F3F4F6;
    --color-on-surface: #1A2332;
    --color-border: #D1D5DB;
    --color-muted: #4A5568;
}
"""
    css_file = make_temp_file(".css", css_content)
    result = parse_tailwind_colors(str(css_file))

    # Spot-check a few of the renamed/new keys.
    assert result["on-surface"] == "#1A2332"
    assert result["error"] == "#E8553D"
    assert result["on-error"] == "#FFFFFF"
    assert result["secondary"] == "#475569"
    assert result["info"] == "#0EA5E9"
    assert result["on-success"] == "#FFFFFF"
    # Legacy names must NOT leak through.
    assert "foreground" not in result
    assert "danger" not in result


def test_parse_tailwind_colors_only_captures_hex_values(make_temp_file):
    """Test that only hex color values are captured."""
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
        "accent": "#FF5733",
    }
