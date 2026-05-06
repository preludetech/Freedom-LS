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
