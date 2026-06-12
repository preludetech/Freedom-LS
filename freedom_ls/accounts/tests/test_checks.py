"""Tests for freedom_ls.accounts system checks."""

from __future__ import annotations

from django.test import override_settings

from freedom_ls.accounts.checks import check_email_colour_tokens

# ---------------------------------------------------------------------------
# check_email_colour_tokens
# ---------------------------------------------------------------------------


def test_all_seven_valid_tokens_produce_no_warnings(make_temp_file) -> None:
    """All seven email colour tokens present and valid → empty warning list."""
    css_content = """
@theme {
    --color-primary: #2B6CB0;
    --color-on-surface: #1A2332;
    --color-muted: #4A5568;
    --color-surface: #FFFFFF;
    --color-surface-2: #F3F4F6;
    --color-on-primary: #FFFFFF;
    --color-border: #D1D5DB;
}
"""
    css_file = make_temp_file(".css", css_content)

    with override_settings(EMAIL_THEME_CSS_PATH=str(css_file)):
        result = check_email_colour_tokens(app_configs=None)

    assert result == []


def test_unconvertible_token_value_yields_warning(make_temp_file) -> None:
    """A token whose raw value cannot be converted to hex yields a Warning naming it."""
    css_content = """
@theme {
    --color-primary: not-a-colour;
    --color-on-surface: #1A2332;
    --color-muted: #4A5568;
    --color-surface: #FFFFFF;
    --color-surface-2: #F3F4F6;
    --color-on-primary: #FFFFFF;
    --color-border: #D1D5DB;
}
"""
    css_file = make_temp_file(".css", css_content)

    with override_settings(EMAIL_THEME_CSS_PATH=str(css_file)):
        result = check_email_colour_tokens(app_configs=None)

    assert len(result) == 1
    assert result[0].id == "freedom_ls_accounts.W002"
    assert "primary" in result[0].msg


def test_missing_token_yields_warning(make_temp_file) -> None:
    """A CSS file missing one of the seven expected tokens yields a Warning for that token."""
    css_content = """
@theme {
    --color-on-surface: #1A2332;
    --color-muted: #4A5568;
    --color-surface: #FFFFFF;
    --color-surface-2: #F3F4F6;
    --color-on-primary: #FFFFFF;
    --color-border: #D1D5DB;
}
"""
    # --color-primary is absent
    css_file = make_temp_file(".css", css_content)

    with override_settings(EMAIL_THEME_CSS_PATH=str(css_file)):
        result = check_email_colour_tokens(app_configs=None)

    assert len(result) == 1
    assert result[0].id == "freedom_ls_accounts.W002"
    assert "primary" in result[0].msg


def test_missing_theme_css_file_does_not_raise(tmp_path) -> None:
    """A missing theme.css causes the check to degrade gracefully without raising."""
    absent_path = str(tmp_path / "nonexistent" / "theme.css")

    with override_settings(EMAIL_THEME_CSS_PATH=absent_path):
        # Must not raise; the check degrades to staying silent.
        result = check_email_colour_tokens(app_configs=None)

    assert result == []


def test_multiple_bad_tokens_each_produce_a_warning(make_temp_file) -> None:
    """Each unconvertible token produces a separate Warning with the token name."""
    css_content = """
@theme {
    --color-primary: not-a-colour;
    --color-on-surface: also-not-a-colour;
    --color-muted: #4A5568;
    --color-surface: #FFFFFF;
    --color-surface-2: #F3F4F6;
    --color-on-primary: #FFFFFF;
    --color-border: #D1D5DB;
}
"""
    css_file = make_temp_file(".css", css_content)

    with override_settings(EMAIL_THEME_CSS_PATH=str(css_file)):
        result = check_email_colour_tokens(app_configs=None)

    assert len(result) == 2
    assert all(w.id == "freedom_ls_accounts.W002" for w in result)
    messages = {w.msg for w in result}
    assert any("primary" in msg for msg in messages)
    assert any("on-surface" in msg for msg in messages)


def test_check_is_registered_with_django() -> None:
    """The colour-token check is registered and discoverable by Django's check framework."""
    from django.core.checks import registry

    registered_names = [check.__name__ for check in registry.registry.registered_checks]
    assert "check_email_colour_tokens" in registered_names
