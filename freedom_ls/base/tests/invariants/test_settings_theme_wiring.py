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


def test_inactive_theme_static_dirs_in_staticfiles_dirs() -> None:
    """Every shipped theme's static/ dir is surfaced so
    ``/static/themes/<slug>/theme.css`` resolves regardless of which theme is
    active. With ``default`` active in the test settings, ``first_class`` must
    still appear (and any other shipped theme on disk).
    """
    shipped_themes_dir = FREEDOM_LS_PACKAGE_DIR / "themes"
    surfaced = {Path(p) for p in settings.STATICFILES_DIRS}
    for theme_dir in shipped_themes_dir.iterdir():
        if not theme_dir.is_dir():
            continue
        static_dir = theme_dir / "static"
        if static_dir.is_dir():
            assert static_dir in surfaced, (
                f"theme {theme_dir.name!r} static/ not in STATICFILES_DIRS"
            )


def test_unknown_theme_slug_raises_improperly_configured() -> None:
    with pytest.raises(ImproperlyConfigured) as exc:
        resolve_theme_dir("does-not-exist", list(settings.FLS_THEMES_DIRS))

    msg = str(exc.value)
    assert "does-not-exist" in msg
