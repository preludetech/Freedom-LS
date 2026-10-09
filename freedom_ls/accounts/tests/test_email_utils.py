"""None"""

import struct
import warnings
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from django.template.loader import render_to_string

from freedom_ls.accounts import email_utils
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
from freedom_ls.accounts.factories import UserFactory


@pytest.fixture(autouse=True)
def _clear_cached_email_lookups() -> Iterator[None]:
    """Clear process-lifetime caches so overrides in a test take effect and don't leak.

    ``get_email_theme`` and ``email_logo_dimensions`` are both ``functools.cache``d
    for the process lifetime; clearing both before and after every test means
    individual tests never need their own try/finally cache-clear dance.
    """
    get_email_theme.cache_clear()
    email_logo_dimensions.cache_clear()
    yield
    get_email_theme.cache_clear()
    email_logo_dimensions.cache_clear()


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
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        result = email_safe_font_stack(raw)
    assert result == expected


def test_email_safe_font_stack_custom_only_emits_warning() -> None:
    """A stack reduced to only the generic emits a UserWarning about custom fonts."""
    with pytest.warns(UserWarning, match="email-safe allowlist"):
        email_safe_font_stack('"DM Sans", system-ui, sans-serif')


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


# ---------------------------------------------------------------------------
# image_dimensions / email_logo_dimensions
# ---------------------------------------------------------------------------

_LOGO_STATIC_PATH = "images/first_class_logo.png"


def test_image_dimensions_reads_png_intrinsic_size(tmp_path: Path) -> None:
    """image_dimensions reads a PNG's intrinsic (width, height) from its header."""
    w, h = 320, 200
    png = tmp_path / "probe.png"
    png.write_bytes(
        b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", w, h)
    )
    assert image_dimensions(str(png)) == (w, h)


def test_image_dimensions_returns_none_for_non_image(make_temp_file) -> None:
    """A non-image file yields None rather than raising."""
    not_an_image = make_temp_file(".css", "--color-primary: #2B6CB0;")
    assert image_dimensions(str(not_an_image)) is None


def test_image_dimensions_returns_none_for_missing_file(tmp_path) -> None:
    """A path that does not exist yields None."""
    assert image_dimensions(str(tmp_path / "nope.png")) is None


def test_email_logo_dimensions_scales_to_display_height(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The logo is scaled to the fixed display height with width preserving ratio."""
    from django.contrib.staticfiles import finders

    # No dependency on any shipped asset: stub the finder to resolve, and feed a
    # controlled native size unrelated to the shipped 512x248 logo.
    monkeypatch.setattr(finders, "find", lambda path: "/nonexistent/logo.png")
    monkeypatch.setattr(email_utils, "image_dimensions", lambda _path: (300, 100))
    # Independent oracle: 300 wide at native height 100, scaled to height 48 -> 144.
    assert email_logo_dimensions(_LOGO_STATIC_PATH) == (144, EMAIL_LOGO_DISPLAY_HEIGHT)


def test_email_logo_dimensions_returns_none_for_unfound_static() -> None:
    """An unresolvable static path yields None (template falls back to height-only)."""
    assert email_logo_dimensions("images/does_not_exist_logo.png") is None


# ---------------------------------------------------------------------------
# get_email_theme
# ---------------------------------------------------------------------------


# A complete, self-contained theme written with sentinel values, so these tests
# exercise get_email_theme's parse/merge/resolve logic without coupling to what
# the real shipped themes happen to be configured with.
_SENTINEL_DEFAULT_CSS = """
@theme {
    --color-primary: #abc123;
    --color-on-primary: #ffffff;
    --color-on-surface: #111111;
    --color-muted: #666666;
    --color-surface: #fefefe;
    --color-surface-2: #eeeeee;
    --color-border: #cccccc;
    --color-header: #abc124;
    --color-on-header: #222222;
    --fls-font-sans: "DM Sans", Arial, sans-serif;
    --fls-radius-md: 0.5rem;
}
"""


def test_get_email_theme_falls_back_to_default_theme_when_active_css_missing(
    tmp_path,
) -> None:
    """A missing *active* theme.css resolves entirely from the default theme."""
    default_css = tmp_path / "default.css"
    default_css.write_text(_SENTINEL_DEFAULT_CSS)
    absent_active = str(tmp_path / "nope" / "theme.css")
    with (
        patch(
            "freedom_ls.accounts.email_utils.default_theme_css_path",
            return_value=str(default_css),
        ),
        patch(
            "freedom_ls.accounts.email_utils.active_theme_css_path",
            return_value=absent_active,
        ),
    ):
        theme = get_email_theme()
    assert theme.color_primary == "#abc123"
    assert theme.color_header == "#abc124"
    assert theme.button_radius == "0.5rem"
    # "DM Sans" is not email-safe and is dropped; Arial survives.
    assert theme.font_family == "Arial, sans-serif"


def test_get_email_theme_overlays_active_theme_over_default(tmp_path) -> None:
    """Tokens in the active theme override the default; absent ones fall through."""
    default_css = tmp_path / "default.css"
    default_css.write_text(_SENTINEL_DEFAULT_CSS)
    active_css = tmp_path / "active.css"
    active_css.write_text("@theme { --color-primary: #def456; }")
    with (
        patch(
            "freedom_ls.accounts.email_utils.default_theme_css_path",
            return_value=str(default_css),
        ),
        patch(
            "freedom_ls.accounts.email_utils.active_theme_css_path",
            return_value=str(active_css),
        ),
    ):
        theme = get_email_theme()
    # Active overrides primary; header (absent from active) stays the default.
    assert theme.color_primary == "#def456"
    assert theme.color_header == "#abc124"


def test_get_email_theme_raises_when_default_theme_css_missing(tmp_path) -> None:
    """A missing *default* theme.css fails loud rather than rendering wrong colours."""
    absent = str(tmp_path / "nope" / "theme.css")
    with (
        patch(
            "freedom_ls.accounts.email_utils.default_theme_css_path",
            return_value=absent,
        ),
        pytest.raises(FileNotFoundError),
    ):
        get_email_theme()


# Integration tests for email templates.
#
# Tests that all email templates render correctly with appropriate context,
# contain expected content, and meet size constraints.


# Fixed sentinel theme values, one per EmailTheme field. These stand in for what
# AccountAdapter.send_mail injects via asdict(get_email_theme()); using fixed
# values (rather than reading the live theme) keeps these template tests from
# breaking whenever a theme is re-skinned. color_primary and color_header are
# deliberately distinct, and font_family keeps a quoted multi-word name so the
# premailer autoescape regression test stays meaningful.
EMAIL_THEME_CONTEXT: dict[str, str] = {
    "color_primary": "#abc123",
    "color_on_primary": "#ffffff",
    "color_foreground": "#111111",
    "color_muted": "#666666",
    "color_surface": "#fefefe",
    "color_surface_2": "#eeeeee",
    "color_border": "#cccccc",
    "color_header": "#abc124",
    "color_on_header": "#222222",
    "font_family": '"Helvetica Neue", Arial, sans-serif',
    "button_radius": "0.375rem",
}


# Base context shared by all email templates; email_label is the branding label.
EMAIL_SETTINGS_CONTEXT: dict[str, str | None] = {
    **EMAIL_THEME_CONTEXT,
    "email_label": "TestSite",
}


# Security context for notification emails
SECURITY_CONTEXT: dict[str, str] = {
    "ip": "192.168.1.100",
    "user_agent": "Mozilla/5.0 TestBrowser",
    "timestamp": "2026-03-01 12:00:00 UTC",
}


# Max allowed size for rendered HTML emails
MAX_EMAIL_SIZE_BYTES = 102_400  # 100KB


@pytest.fixture
def base_context(mock_site_context: object) -> dict[str, object]:
    """Provide base context for rendering email templates."""
    return {
        **EMAIL_SETTINGS_CONTEXT,
        "current_site": mock_site_context,
    }


# ---------------------------------------------------------------------------
# 1. Base template rendering tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBaseEmailTemplate:
    """Tests for emails/base_email.html base template."""

    def test_base_email_contains_table_layout(
        self, base_context: dict[str, object]
    ) -> None:
        """Base email should use table-based layout with role=presentation."""
        html = render_to_string("emails/base_email.html", base_context)
        assert 'role="presentation"' in html

    def test_base_email_contains_brand_colors(
        self, base_context: dict[str, object]
    ) -> None:
        """Base email header should carry the theme's header background and text colors.

        (color_primary is inlined only onto buttons/links, which the bare base
        template has none of — premailer strips the unused rule — so the
        reliably-rendered brand colors here are the header pair.)
        """
        html = render_to_string("emails/base_email.html", base_context)
        assert EMAIL_THEME_CONTEXT["color_header"] in html
        assert EMAIL_THEME_CONTEXT["color_on_header"] in html

    def test_base_email_contains_site_name(
        self, base_context: dict[str, object]
    ) -> None:
        """Base email should display the site name."""
        html = render_to_string("emails/base_email.html", base_context)
        assert "TestSite" in html

    def test_base_email_footer_contains_copyright(
        self, base_context: dict[str, object]
    ) -> None:
        """Base email footer should contain a copyright symbol."""
        html = render_to_string("emails/base_email.html", base_context)
        # The &copy; entity or the actual copyright symbol should be present
        assert "&copy;" in html or "\u00a9" in html

    def test_base_email_size_under_limit(self, base_context: dict[str, object]) -> None:
        """Base email HTML should be under 100KB."""
        html = render_to_string("emails/base_email.html", base_context)
        assert len(html.encode("utf-8")) < MAX_EMAIL_SIZE_BYTES

    def test_base_email_declares_font_family(
        self, base_context: dict[str, object]
    ) -> None:
        """The rendered (premailer-inlined) email must carry a font-family.

        Regression for the autoescape bug: quoted family names like
        "Helvetica Neue" were escaped to &quot; inside the <style> block,
        which cssutils could not parse, so premailer silently dropped the
        whole font-family property and the body fell back to the client's
        default serif.
        """
        html = render_to_string("emails/base_email.html", base_context)
        assert "font-family" in html
        # A representative family from the configured stack should survive.
        assert "Helvetica Neue" in html or "Arial" in html


# ---------------------------------------------------------------------------
# 2. Notification template rendering tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestNotificationBaseTemplate:
    """Tests for emails/base_notification_email.html."""

    def test_notification_contains_security_information_heading(
        self, base_context: dict[str, object]
    ) -> None:
        """Notification email should include Security Information section."""
        context = {**base_context, **SECURITY_CONTEXT}
        html = render_to_string("emails/base_notification_email.html", context)
        assert "Security Information" in html

    def test_notification_contains_ip_address(
        self, base_context: dict[str, object]
    ) -> None:
        """Notification email should display the IP address."""
        context = {**base_context, **SECURITY_CONTEXT}
        html = render_to_string("emails/base_notification_email.html", context)
        assert "192.168.1.100" in html

    def test_notification_contains_user_agent(
        self, base_context: dict[str, object]
    ) -> None:
        """Notification email should display the browser/user agent."""
        context = {**base_context, **SECURITY_CONTEXT}
        html = render_to_string("emails/base_notification_email.html", context)
        assert "Mozilla/5.0 TestBrowser" in html

    def test_notification_contains_timestamp(
        self, base_context: dict[str, object]
    ) -> None:
        """Notification email should display the timestamp."""
        context = {**base_context, **SECURITY_CONTEXT}
        html = render_to_string("emails/base_notification_email.html", context)
        assert "2026-03-01 12:00:00 UTC" in html


# ---------------------------------------------------------------------------
# 3. Allauth email type rendering tests (parametrized)
# ---------------------------------------------------------------------------

# Each tuple: (template_name, extra_context, expected_html_snippets, expected_txt_snippets, expected_subject)
ALLAUTH_EMAIL_TYPES: list[tuple[str, dict[str, str], list[str], list[str], str]] = [
    (
        "email_confirmation",
        {
            "activate_url": "https://testsite/confirm/abc123",
            "key": "abc123",  # pragma: allowlist secret
        },
        ["https://testsite/confirm/abc123", "Confirm Email Address"],
        ["https://testsite/confirm/abc123", "Confirm Email Address"],
        "Confirm your email address",
    ),
    (
        "email_confirmation_signup",
        {
            "activate_url": "https://testsite/confirm/signup456",
            "key": "signup456",  # pragma: allowlist secret
        },
        ["https://testsite/confirm/signup456", "Confirm Email Address"],
        ["https://testsite/confirm/signup456", "Confirm Email Address"],
        "Confirm your email address",
    ),
    (
        "password_reset_key",
        {
            "password_reset_url": "https://testsite/reset/key789",  # pragma: allowlist secret
        },
        ["https://testsite/reset/key789", "Reset Password"],
        ["https://testsite/reset/key789", "Reset Password"],
        "Reset your password",
    ),
    (
        "unknown_account",
        {
            "email": "unknown@example.com",
            "signup_url": "https://testsite/signup",
        },
        ["unknown@example.com", "https://testsite/signup", "Create an Account"],
        ["unknown@example.com", "https://testsite/signup", "Create an Account"],
        "Password reset request",
    ),
    (
        "login_code",
        {
            "code": "847293",
            "email": "user@example.com",
        },
        ["847293"],
        ["847293"],
        "Your login code",
    ),
    (
        "account_already_exists",
        {
            "email": "existing@example.com",
            "password_reset_url": "https://testsite/reset",  # pragma: allowlist secret
            "signup_url": "https://testsite/signup",
        },
        ["existing@example.com", "https://testsite/reset", "Reset Password"],
        ["existing@example.com", "https://testsite/reset", "Reset Password"],
        "Account already exists",
    ),
]


NOTIFICATION_EMAIL_TYPES: list[
    tuple[str, dict[str, str], list[str], list[str], str]
] = [
    (
        "password_changed",
        {},
        ["password has been changed"],
        ["password has been changed"],
        "Your password has been changed",
    ),
    (
        "password_set",
        {},
        ["password has been set"],
        ["password has been set"],
        "A password has been set for your account",
    ),
    (
        "email_changed",
        {
            "from_email": "old@example.com",
            "to_email": "new@example.com",
        },
        ["old@example.com", "new@example.com", "email address has been changed"],
        ["old@example.com", "new@example.com", "email address has been changed"],
        "Your email address has been changed",
    ),
    (
        "email_confirm",
        {},
        ["email address has been confirmed"],
        ["email address has been confirmed"],
        "Your email address has been confirmed",
    ),
    (
        "email_deleted",
        {
            "deleted_email": "removed@example.com",
        },
        ["removed@example.com", "has been removed"],
        ["removed@example.com", "has been removed"],
        "An email address has been removed from your account",
    ),
]


@pytest.mark.django_db
class TestAllauthMessageEmails:
    """Tests for allauth message-type email templates (non-notification)."""

    @pytest.mark.parametrize(
        (
            "template_name",
            "extra_context",
            "expected_html_snippets",
            "expected_txt_snippets",
            "expected_subject",
        ),
        ALLAUTH_EMAIL_TYPES,
        ids=[t[0] for t in ALLAUTH_EMAIL_TYPES],
    )
    def test_html_template_renders_with_expected_content(
        self,
        base_context: dict[str, object],
        template_name: str,
        extra_context: dict[str, str],
        expected_html_snippets: list[str],
        expected_txt_snippets: list[str],
        expected_subject: str,
    ) -> None:
        """HTML message template should render and contain expected content."""
        user = UserFactory(first_name="Alice", last_name="Smith")
        context = {**base_context, "user": user, **extra_context}
        html = render_to_string(f"account/email/{template_name}_message.html", context)

        assert html.strip(), f"HTML template for {template_name} rendered empty"
        for snippet in expected_html_snippets:
            assert snippet in html, (
                f"Expected '{snippet}' in {template_name} HTML output"
            )

    @pytest.mark.parametrize(
        (
            "template_name",
            "extra_context",
            "expected_html_snippets",
            "expected_txt_snippets",
            "expected_subject",
        ),
        ALLAUTH_EMAIL_TYPES,
        ids=[t[0] for t in ALLAUTH_EMAIL_TYPES],
    )
    def test_txt_template_renders_with_expected_content(
        self,
        base_context: dict[str, object],
        template_name: str,
        extra_context: dict[str, str],
        expected_html_snippets: list[str],
        expected_txt_snippets: list[str],
        expected_subject: str,
    ) -> None:
        """Text message template should render and contain expected content."""
        user = UserFactory(first_name="Alice", last_name="Smith")
        context = {**base_context, "user": user, **extra_context}
        txt = render_to_string(f"account/email/{template_name}_message.txt", context)

        assert txt.strip(), f"Text template for {template_name} rendered empty"
        for snippet in expected_txt_snippets:
            assert snippet in txt, (
                f"Expected '{snippet}' in {template_name} text output"
            )

    @pytest.mark.parametrize(
        (
            "template_name",
            "extra_context",
            "expected_html_snippets",
            "expected_txt_snippets",
            "expected_subject",
        ),
        ALLAUTH_EMAIL_TYPES,
        ids=[t[0] for t in ALLAUTH_EMAIL_TYPES],
    )
    def test_subject_line_is_correct(
        self,
        base_context: dict[str, object],
        template_name: str,
        extra_context: dict[str, str],
        expected_html_snippets: list[str],
        expected_txt_snippets: list[str],
        expected_subject: str,
    ) -> None:
        """Subject line template should render the correct subject text."""
        context = {**base_context, **extra_context}
        subject = render_to_string(
            f"account/email/{template_name}_subject.txt", context
        ).strip()
        assert subject == expected_subject


@pytest.mark.django_db
class TestAllauthNotificationEmails:
    """Tests for allauth notification-type email templates (with security info)."""

    @pytest.mark.parametrize(
        (
            "template_name",
            "extra_context",
            "expected_html_snippets",
            "expected_txt_snippets",
            "expected_subject",
        ),
        NOTIFICATION_EMAIL_TYPES,
        ids=[t[0] for t in NOTIFICATION_EMAIL_TYPES],
    )
    def test_html_notification_renders_with_expected_content(
        self,
        base_context: dict[str, object],
        template_name: str,
        extra_context: dict[str, str],
        expected_html_snippets: list[str],
        expected_txt_snippets: list[str],
        expected_subject: str,
    ) -> None:
        """HTML notification template should render and contain expected content."""
        user = UserFactory(first_name="Alice", last_name="Smith")
        context = {
            **base_context,
            "user": user,
            **SECURITY_CONTEXT,
            **extra_context,
        }
        html = render_to_string(f"account/email/{template_name}_message.html", context)

        assert html.strip(), f"HTML template for {template_name} rendered empty"
        for snippet in expected_html_snippets:
            assert snippet in html, (
                f"Expected '{snippet}' in {template_name} HTML output"
            )

    @pytest.mark.parametrize(
        (
            "template_name",
            "extra_context",
            "expected_html_snippets",
            "expected_txt_snippets",
            "expected_subject",
        ),
        NOTIFICATION_EMAIL_TYPES,
        ids=[t[0] for t in NOTIFICATION_EMAIL_TYPES],
    )
    def test_txt_notification_renders_with_expected_content(
        self,
        base_context: dict[str, object],
        template_name: str,
        extra_context: dict[str, str],
        expected_html_snippets: list[str],
        expected_txt_snippets: list[str],
        expected_subject: str,
    ) -> None:
        """Text notification template should render and contain expected content."""
        user = UserFactory(first_name="Alice", last_name="Smith")
        context = {
            **base_context,
            "user": user,
            **SECURITY_CONTEXT,
            **extra_context,
        }
        txt = render_to_string(f"account/email/{template_name}_message.txt", context)

        assert txt.strip(), f"Text template for {template_name} rendered empty"
        for snippet in expected_txt_snippets:
            assert snippet in txt, (
                f"Expected '{snippet}' in {template_name} text output"
            )

    @pytest.mark.parametrize(
        (
            "template_name",
            "extra_context",
            "expected_html_snippets",
            "expected_txt_snippets",
            "expected_subject",
        ),
        NOTIFICATION_EMAIL_TYPES,
        ids=[t[0] for t in NOTIFICATION_EMAIL_TYPES],
    )
    def test_notification_subject_line_is_correct(
        self,
        base_context: dict[str, object],
        template_name: str,
        extra_context: dict[str, str],
        expected_html_snippets: list[str],
        expected_txt_snippets: list[str],
        expected_subject: str,
    ) -> None:
        """Subject line for notification emails should be correct."""
        context = {**base_context, **extra_context}
        subject = render_to_string(
            f"account/email/{template_name}_subject.txt", context
        ).strip()
        assert subject == expected_subject

    @pytest.mark.parametrize(
        (
            "template_name",
            "extra_context",
            "expected_html_snippets",
            "expected_txt_snippets",
            "expected_subject",
        ),
        NOTIFICATION_EMAIL_TYPES,
        ids=[t[0] for t in NOTIFICATION_EMAIL_TYPES],
    )
    def test_notification_html_contains_security_info(
        self,
        base_context: dict[str, object],
        template_name: str,
        extra_context: dict[str, str],
        expected_html_snippets: list[str],
        expected_txt_snippets: list[str],
        expected_subject: str,
    ) -> None:
        """Notification HTML emails should include security information section."""
        user = UserFactory(first_name="Alice", last_name="Smith")
        context = {
            **base_context,
            "user": user,
            **SECURITY_CONTEXT,
            **extra_context,
        }
        html = render_to_string(f"account/email/{template_name}_message.html", context)

        assert "Security Information" in html
        assert SECURITY_CONTEXT["ip"] in html
        assert SECURITY_CONTEXT["user_agent"] in html
        assert SECURITY_CONTEXT["timestamp"] in html


# ---------------------------------------------------------------------------
# 4. Header logo / label tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestHeaderLogo:
    """Tests for logo vs text rendering in the email header, driven by email_logo_url."""

    def test_header_shows_img_with_absolute_src_when_logo_url_is_set(
        self, base_context: dict[str, object]
    ) -> None:
        """When email_logo_url is an absolute URL, rendered HTML contains <img src> with that URL."""
        logo_url = "https://example.com/static/images/logo.png"
        context = {**base_context, "email_logo_url": logo_url}
        html = render_to_string("emails/base_email.html", context)
        assert "<img" in html
        assert logo_url in html

    def test_header_img_src_is_absolute_url_not_bare_static_path(
        self, base_context: dict[str, object]
    ) -> None:
        """The img src must be a fully-qualified URL, never a bare /static/ path."""
        logo_url = "https://example.com/static/images/logo.png"
        context = {**base_context, "email_logo_url": logo_url}
        html = render_to_string("emails/base_email.html", context)
        # The absolute URL should appear in the src attribute
        assert 'src="https://example.com/static/images/logo.png"' in html

    def test_header_img_alt_equals_email_label(
        self, base_context: dict[str, object]
    ) -> None:
        """When email_logo_url is set, the img alt attribute should equal email_label."""
        logo_url = "https://example.com/static/images/logo.png"
        context = {**base_context, "email_logo_url": logo_url, "email_label": "MyBrand"}
        html = render_to_string("emails/base_email.html", context)
        assert 'alt="MyBrand"' in html

    def test_header_shows_h1_text_label_when_logo_url_is_none(
        self, base_context: dict[str, object]
    ) -> None:
        """When email_logo_url is None, header shows the email_label in an h1 and no img."""
        context = {**base_context, "email_logo_url": None, "email_label": "MyBrand"}
        html = render_to_string("emails/base_email.html", context)
        assert "<h1" in html
        assert "MyBrand" in html
        assert "<img" not in html

    def test_header_shows_no_img_when_email_logo_url_absent(
        self, base_context: dict[str, object]
    ) -> None:
        """Without email_logo_url in context at all, no img tag appears."""
        # base_context has no email_logo_url key
        context = {k: v for k, v in base_context.items() if k != "email_logo_url"}
        html = render_to_string("emails/base_email.html", context)
        assert "<img" not in html

    def test_header_text_fallback_uses_current_site_name_when_no_email_label(
        self, base_context: dict[str, object]
    ) -> None:
        """Back-compat: without email_label in context, the site name from current_site is shown."""
        context = {k: v for k, v in base_context.items() if k != "email_label"}
        context["email_logo_url"] = None
        html = render_to_string("emails/base_email.html", context)
        assert "TestSite" in html

    def test_plain_text_contains_email_label_and_no_static_url(
        self, base_context: dict[str, object]
    ) -> None:
        """Plain-text base template contains email_label and no /static/ URL."""
        context = {**base_context, "email_label": "BrandName"}
        txt = render_to_string("emails/base_email.txt", context)
        assert "BrandName" in txt
        assert "/static/" not in txt

    def test_plain_text_falls_back_to_site_name_without_email_label(
        self, base_context: dict[str, object]
    ) -> None:
        """Back-compat: plain text shows current_site.name when email_label not in context."""
        context = {k: v for k, v in base_context.items() if k != "email_label"}
        txt = render_to_string("emails/base_email.txt", context)
        assert "TestSite" in txt

    def test_logo_img_uses_computed_width_and_height_when_provided(
        self, base_context: dict[str, object]
    ) -> None:
        """Given logo dimensions, the img carries matching width/height and no max-height."""
        context = {
            **base_context,
            "email_logo_url": "https://example.com/static/images/logo.png",
            "email_logo_width": 99,
            "email_logo_height": 48,
        }
        html = render_to_string("emails/base_email.html", context)
        assert 'width="99"' in html
        assert 'height="48"' in html
        # The stretch-prone max-height constraint must be gone.
        assert "max-height" not in html

    def test_logo_img_falls_back_to_height_only_without_dimensions(
        self, base_context: dict[str, object]
    ) -> None:
        """Without computed dimensions, the img is constrained by height with width auto."""
        context = {
            **base_context,
            "email_logo_url": "https://example.com/static/images/logo.png",
            "email_logo_width": None,
            "email_logo_height": None,
        }
        html = render_to_string("emails/base_email.html", context)
        assert "<img" in html
        assert 'height="48"' in html
        assert "width: auto" in html


# ---------------------------------------------------------------------------
# 4b. Adapter-level tests for send_mail context composition
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAdapterSendMailContext:
    """Tests that AccountAdapter.send_mail injects email_logo_url and email_label."""

    @staticmethod
    def _capture_send_mail_context(mock_site_context) -> dict:
        """Run AccountAdapter.send_mail with no request and return the rendered context.

        render_mail is patched to capture the context dict the adapter composes,
        and the allauth request context is forced to None (mail sent outside a
        web request). FORCE_SITE_NAME is pinned to the fixture's site because it
        is the only thing that names a tenant without a request -- unpinned, the
        adapter refuses to send rather than guess which tenant it is branding.
        """
        from unittest.mock import MagicMock, patch

        from django.test import override_settings

        from freedom_ls.accounts.allauth_account_adapter import AccountAdapter

        captured: dict = {}
        adapter = AccountAdapter(request=None)

        with (
            override_settings(FORCE_SITE_NAME=mock_site_context.name),
            patch.object(adapter, "render_mail") as mock_render_mail,
            patch(
                "freedom_ls.accounts.allauth_account_adapter.allauth_context"
            ) as mock_ctx,
        ):
            mock_ctx.request = None

            def capture_ctx(template_prefix, email, ctx):
                captured.update(ctx)
                m = MagicMock()
                m.send = MagicMock()
                return m

            mock_render_mail.side_effect = capture_ctx
            adapter.send_mail("account/email/login_code", "user@example.com", {})

        return captured

    def test_send_mail_injects_absolute_logo_url_when_logo_path_set(
        self, mock_site_context, settings
    ) -> None:
        """send_mail should compose an absolute http(s)://domain/static/path URL for email_logo_url."""
        settings.EMAIL_LOGO_STATIC_PATH = "images/test_logo.png"
        settings.HEADER_LOGO_STATIC_PATH = None
        settings.HEADER_TITLE = ""
        settings.ACCOUNT_DEFAULT_HTTP_PROTOCOL = "http"

        captured = self._capture_send_mail_context(mock_site_context)

        assert "email_logo_url" in captured
        logo_url = captured["email_logo_url"]
        assert logo_url is not None
        # Must be absolute: starts with http:// or https://
        assert logo_url.startswith("http://") or logo_url.startswith("https://")
        # Must contain the static path
        assert "images/test_logo.png" in logo_url

    def test_send_mail_logo_url_is_none_when_no_logo_paths_set(
        self, mock_site_context, settings
    ) -> None:
        """send_mail sets email_logo_url to None when no logo path is configured."""
        settings.EMAIL_LOGO_STATIC_PATH = None
        settings.HEADER_LOGO_STATIC_PATH = None
        settings.HEADER_TITLE = ""

        captured = self._capture_send_mail_context(mock_site_context)

        assert captured.get("email_logo_url") is None

    def test_send_mail_email_label_uses_header_title_when_set(
        self, mock_site_context, settings
    ) -> None:
        """send_mail sets email_label to HEADER_TITLE when it is configured."""
        settings.HEADER_TITLE = "MyProduct"
        settings.EMAIL_LOGO_STATIC_PATH = None
        settings.HEADER_LOGO_STATIC_PATH = None

        captured = self._capture_send_mail_context(mock_site_context)

        assert captured.get("email_label") == "MyProduct"

    def test_send_mail_email_label_falls_back_to_site_name_when_no_header_title(
        self, mock_site_context, settings
    ) -> None:
        """send_mail falls back to current_site.name for email_label when HEADER_TITLE is empty."""
        settings.HEADER_TITLE = ""
        settings.EMAIL_LOGO_STATIC_PATH = None
        settings.HEADER_LOGO_STATIC_PATH = None

        captured = self._capture_send_mail_context(mock_site_context)

        # Should fall back to site name (mock_site_context creates "TestSite")
        assert captured.get("email_label") == "TestSite"

    def test_send_mail_uses_header_logo_path_when_email_logo_path_unset(
        self, mock_site_context, settings
    ) -> None:
        """send_mail falls back to HEADER_LOGO_STATIC_PATH when EMAIL_LOGO_STATIC_PATH is None."""
        settings.EMAIL_LOGO_STATIC_PATH = None
        settings.HEADER_LOGO_STATIC_PATH = "images/header_logo.png"
        settings.HEADER_TITLE = ""
        settings.ACCOUNT_DEFAULT_HTTP_PROTOCOL = "http"

        captured = self._capture_send_mail_context(mock_site_context)

        logo_url = captured.get("email_logo_url")
        assert logo_url is not None
        assert "images/header_logo.png" in logo_url


# ---------------------------------------------------------------------------
# 5. Greeting personalization test
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCtaButtonRadius:
    """CTA buttons must use the theme-driven radius, not a hardcoded value."""

    CTA_TEMPLATES: list[tuple[str, dict[str, str]]] = [
        (
            "email_confirmation",
            {"activate_url": "https://testsite/confirm", "key": "k"},
        ),
        (
            "password_reset_key",
            {
                "password_reset_url": "https://testsite/reset",  # pragma: allowlist secret
            },
        ),
        (
            "account_already_exists",
            {
                "email": "e@example.com",
                "password_reset_url": "https://testsite/reset",  # pragma: allowlist secret
                "signup_url": "https://testsite/signup",
            },
        ),
        (
            "unknown_account",
            {"email": "e@example.com", "signup_url": "https://testsite/signup"},
        ),
    ]

    @pytest.mark.parametrize(
        ("template_name", "extra_context"),
        CTA_TEMPLATES,
        ids=[t[0] for t in CTA_TEMPLATES],
    )
    def test_cta_uses_button_radius_not_hardcoded(
        self,
        base_context: dict[str, object],
        template_name: str,
        extra_context: dict[str, str],
    ) -> None:
        """The CTA button carries the resolved radius and never a hardcoded 6px."""
        user = UserFactory(first_name="Alice", last_name="Smith")
        context = {
            **base_context,
            "user": user,
            "button_radius": "13px",  # distinctive sentinel
            **extra_context,
        }
        html = render_to_string(f"account/email/{template_name}_message.html", context)
        assert "border-radius: 13px" in html
        assert "border-radius: 6px" not in html


@pytest.mark.django_db
class TestBodyBrandLabel:
    """Message bodies should refer to the brand label, not the raw site name."""

    @pytest.mark.parametrize(
        ("template_name", "extra_context"),
        [
            (
                "password_reset_key",
                {
                    "password_reset_url": "https://testsite/reset/k",  # pragma: allowlist secret
                },
            ),
            (
                "account_already_exists",
                {
                    "email": "e@example.com",
                    "password_reset_url": "https://testsite/reset",  # pragma: allowlist secret
                    "signup_url": "https://testsite/signup",
                },
            ),
            (
                "unknown_account",
                {"email": "e@example.com", "signup_url": "https://testsite/signup"},
            ),
        ],
    )
    def test_body_uses_email_label_over_site_name(
        self,
        base_context: dict[str, object],
        template_name: str,
        extra_context: dict[str, str],
    ) -> None:
        """The body shows email_label (brand) even when it differs from the site name."""
        user = UserFactory(first_name="Alice", last_name="Smith")
        context = {
            **base_context,
            "user": user,
            "email_label": "BrandCo",
            **extra_context,
        }
        html = render_to_string(f"account/email/{template_name}_message.html", context)
        # mock_site_context name is "TestSite"; the body must use the brand label.
        assert "BrandCo" in html
        assert "exists on TestSite" not in html
        assert "account at TestSite" not in html


@pytest.mark.django_db
class TestGreetingPersonalization:
    """Tests for personalized greeting in emails."""

    def test_greeting_includes_first_name_when_present(
        self,
        base_context: dict[str, object],
    ) -> None:
        """Greeting should say 'Hi Alice,' when user has a first name."""
        user = UserFactory(first_name="Alice", last_name="Smith")
        context = {**base_context, "user": user}
        html = render_to_string("emails/base_email.html", context)
        assert "Hi Alice," in html

    def test_greeting_omits_name_when_no_first_name(
        self,
        base_context: dict[str, object],
    ) -> None:
        """Greeting should say 'Hi,' when user has no first name."""
        user = UserFactory(first_name="", last_name="")
        context = {**base_context, "user": user}
        html = render_to_string("emails/base_email.html", context)
        assert "Hi," in html
        # Should not have "Hi ," with extra space
        assert "Hi ," not in html


# ---------------------------------------------------------------------------
# 6. Size test for all HTML emails
# ---------------------------------------------------------------------------

ALL_HTML_TEMPLATES: list[tuple[str, dict[str, str]]] = [
    (
        "account/email/email_confirmation_message.html",
        {
            "activate_url": "https://example.com/confirm",
            "key": "abc",  # pragma: allowlist secret
        },
    ),
    (
        "account/email/email_confirmation_signup_message.html",
        {
            "activate_url": "https://example.com/confirm",
            "key": "abc",  # pragma: allowlist secret
        },
    ),
    (
        "account/email/password_reset_key_message.html",
        {"password_reset_url": "https://example.com/reset"},
    ),
    (
        "account/email/unknown_account_message.html",
        {"email": "test@example.com", "signup_url": "https://example.com/signup"},
    ),
    (
        "account/email/login_code_message.html",
        {"code": "123456", "email": "test@example.com"},
    ),
    (
        "account/email/account_already_exists_message.html",
        {
            "email": "test@example.com",
            "password_reset_url": "https://example.com/reset",
            "signup_url": "https://example.com/signup",
        },
    ),
    ("account/email/password_changed_message.html", {**SECURITY_CONTEXT}),
    ("account/email/password_set_message.html", {**SECURITY_CONTEXT}),
    (
        "account/email/email_changed_message.html",
        {
            "from_email": "old@example.com",
            "to_email": "new@example.com",
            **SECURITY_CONTEXT,
        },
    ),
    ("account/email/email_confirm_message.html", {**SECURITY_CONTEXT}),
    (
        "account/email/email_deleted_message.html",
        {"deleted_email": "removed@example.com", **SECURITY_CONTEXT},
    ),
]


@pytest.mark.django_db
class TestEmailSizeConstraints:
    """Tests that all rendered HTML emails stay under the 100KB limit."""

    @pytest.mark.parametrize(
        ("template_path", "extra_context"),
        ALL_HTML_TEMPLATES,
        ids=[
            t[0].split("/")[-1].replace("_message.html", "") for t in ALL_HTML_TEMPLATES
        ],
    )
    def test_html_email_under_100kb(
        self,
        base_context: dict[str, object],
        template_path: str,
        extra_context: dict[str, str],
    ) -> None:
        """Each HTML email template should render to less than 100KB."""
        user = UserFactory(first_name="Alice", last_name="Smith")
        context = {**base_context, "user": user, **extra_context}
        html = render_to_string(template_path, context)
        size = len(html.encode("utf-8"))
        assert size < MAX_EMAIL_SIZE_BYTES, (
            f"{template_path} rendered to {size} bytes, exceeding {MAX_EMAIL_SIZE_BYTES} byte limit"
        )
