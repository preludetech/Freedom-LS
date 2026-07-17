"""Theme and icon resolution probes.

Both call FLS's own production resolution code so the probes can't drift from
runtime behaviour.
"""

from __future__ import annotations

from django.conf import settings

__all__ = ["test_active_icon_set_resolves", "test_active_theme_resolves"]


def test_active_theme_resolves() -> None:
    from freedom_ls.base.theming import resolve_theme_dir

    resolved = resolve_theme_dir(settings.FLS_THEME, settings.FLS_THEMES_DIRS)
    assert resolved.is_dir()


def test_active_icon_set_resolves() -> None:
    from freedom_ls.icons.config import config as icons_config
    from freedom_ls.icons.mappings import ICON_SETS
    from freedom_ls.icons.render import render_icon

    icon_set = icons_config.FREEDOM_LS_ICON_SET
    assert icon_set in ICON_SETS

    svg = render_icon("", default_semantic="home")
    assert "<svg" in svg
