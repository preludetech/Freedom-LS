"""Tests that ``config/settings_base.py`` wires the active theme correctly.

These tests do not import the settings module directly — they assert the
post-import effects on Django's live settings, plus a direct call to
``resolve_theme_dir`` to pin the failure mode for an unknown slug.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from freedom_ls.base.theming import (
    FREEDOM_LS_PACKAGE_DIR,
    resolve_theme_dir,
)


def test_default_theme_has_no_templates_dir() -> None:
    """Phase 1 ships a Tier-1-only theme — no templates/ subdir."""
    default_theme = FREEDOM_LS_PACKAGE_DIR / "themes" / "default"
    assert default_theme.is_dir()
    assert not (default_theme / "templates").exists()


def test_default_theme_static_dir_in_staticfiles_dirs() -> None:
    """The resolver prepends the theme's static dir to STATICFILES_DIRS."""
    expected = FREEDOM_LS_PACKAGE_DIR / "themes" / "default" / "static"
    assert Path(expected) in [Path(p) for p in settings.STATICFILES_DIRS]


def test_default_theme_templates_dir_not_in_template_dirs() -> None:
    """Default has no templates/, so its path must not appear in TEMPLATES."""
    expected = FREEDOM_LS_PACKAGE_DIR / "themes" / "default" / "templates"
    assert str(expected) not in settings.TEMPLATES[0].get("DIRS", [])


def test_resolved_theme_dir_setting_points_at_default() -> None:
    expected = FREEDOM_LS_PACKAGE_DIR / "themes" / "default"
    assert Path(settings.RESOLVED_THEME_DIR) == expected


def test_unknown_theme_slug_raises_improperly_configured() -> None:
    with pytest.raises(ImproperlyConfigured) as exc:
        resolve_theme_dir("does-not-exist", list(settings.FLS_THEMES_DIRS))

    msg = str(exc.value)
    assert "does-not-exist" in msg
