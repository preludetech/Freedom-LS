"""Tests for freedom_ls.accounts system checks."""

from __future__ import annotations

from unittest.mock import patch

from freedom_ls.accounts.checks import check_email_colour_tokens

# ---------------------------------------------------------------------------
# check_email_colour_tokens
#
# The check builds the same merged token map get_email_theme uses — the default
# theme as a baseline with the active theme layered on top. The default theme is
# real (not patched); _patch_css_path overrides only the *active* theme, so a
# token absent from the active theme is supplied by the default and is not an
# error. An unresolvable token (present but bad, in either theme) is an Error.
# ---------------------------------------------------------------------------


def _patch_css_path(path: str):
    """Patch the resolver so the check reads the given *active* theme.css path."""
    return patch(
        "freedom_ls.accounts.email_utils.active_theme_css_path",
        return_value=str(path),
    )


def test_all_valid_tokens_produce_no_errors(make_temp_file) -> None:
    """All email colour tokens present and valid → empty error list."""
    css_content = """
@theme {
    --color-primary: #2B6CB0;
    --color-on-surface: #1A2332;
    --color-muted: #4A5568;
    --color-surface: #FFFFFF;
    --color-surface-2: #F3F4F6;
    --color-on-primary: #FFFFFF;
    --color-border: #D1D5DB;
    --color-header: #2B6CB0;
    --color-on-header: #FFFFFF;
}
"""
    css_file = make_temp_file(".css", css_content)

    with _patch_css_path(css_file):
        result = check_email_colour_tokens(app_configs=None)

    assert result == []


def test_unconvertible_token_value_yields_error(make_temp_file) -> None:
    """A token whose raw value cannot be converted to hex yields an Error naming it."""
    css_content = """
@theme {
    --color-primary: not-a-colour;
    --color-on-surface: #1A2332;
    --color-muted: #4A5568;
    --color-surface: #FFFFFF;
    --color-surface-2: #F3F4F6;
    --color-on-primary: #FFFFFF;
    --color-border: #D1D5DB;
    --color-header: #2B6CB0;
    --color-on-header: #FFFFFF;
}
"""
    css_file = make_temp_file(".css", css_content)

    with _patch_css_path(css_file):
        result = check_email_colour_tokens(app_configs=None)

    assert len(result) == 1
    assert result[0].id == "freedom_ls_accounts.E002"
    assert "primary" in result[0].msg


def test_token_missing_from_active_theme_falls_back_to_default(make_temp_file) -> None:
    """A token absent from the active theme is supplied by the default — no error."""
    css_content = """
@theme {
    --color-on-surface: #1A2332;
    --color-muted: #4A5568;
    --color-surface: #FFFFFF;
    --color-surface-2: #F3F4F6;
    --color-on-primary: #FFFFFF;
    --color-border: #D1D5DB;
    --color-header: #2B6CB0;
    --color-on-header: #FFFFFF;
}
"""
    # --color-primary is absent from the active theme but present in the default.
    css_file = make_temp_file(".css", css_content)

    with _patch_css_path(css_file):
        result = check_email_colour_tokens(app_configs=None)

    assert result == []


def test_missing_active_theme_css_file_falls_back_to_default(tmp_path) -> None:
    """A missing active theme.css resolves entirely from the default — no error, no raise."""
    absent_path = str(tmp_path / "nonexistent" / "theme.css")

    with _patch_css_path(absent_path):
        result = check_email_colour_tokens(app_configs=None)

    assert result == []


def test_multiple_bad_tokens_each_produce_an_error(make_temp_file) -> None:
    """Each unconvertible token produces a separate Error with the token name."""
    css_content = """
@theme {
    --color-primary: not-a-colour;
    --color-on-surface: also-not-a-colour;
    --color-muted: #4A5568;
    --color-surface: #FFFFFF;
    --color-surface-2: #F3F4F6;
    --color-on-primary: #FFFFFF;
    --color-border: #D1D5DB;
    --color-header: #2B6CB0;
    --color-on-header: #FFFFFF;
}
"""
    css_file = make_temp_file(".css", css_content)

    with _patch_css_path(css_file):
        result = check_email_colour_tokens(app_configs=None)

    assert len(result) == 2
    assert all(e.id == "freedom_ls_accounts.E002" for e in result)
    messages = {e.msg for e in result}
    assert any("primary" in msg for msg in messages)
    assert any("on-surface" in msg for msg in messages)


def test_check_is_registered_with_django() -> None:
    """The colour-token check is registered and discoverable by Django's check framework."""
    from django.core.checks import registry

    registered_names = [check.__name__ for check in registry.registry.registered_checks]
    assert "check_email_colour_tokens" in registered_names
