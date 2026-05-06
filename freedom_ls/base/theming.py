"""Theme resolution for FLS.

This module is intentionally a thin pure-Python utility so it can be unit-tested
without spinning up the Django test client. It is consumed from
``config/settings_base.py`` to wire the active theme into ``TEMPLATES`` and
``STATICFILES_DIRS`` at startup.

A theme is a sparse directory: only ``static/themes/<slug>/theme.css`` is
conventionally required. Themes may optionally ship ``templates/`` and other
static assets. See ``spec_dd/.../themable-implementations-phase-1.../1. spec.md``
for the full token contract and directory shape.
"""

from __future__ import annotations

from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

# Absolute path of the ``freedom_ls/`` package directory. Used by settings to
# build the default search path for themes shipped inside the FLS package.
FREEDOM_LS_PACKAGE_DIR: Path = Path(__file__).resolve().parent.parent


def resolve_theme_dir(theme_slug: str, themes_dirs: list[Path]) -> Path:
    """Return the first ``<parent>/<theme_slug>`` directory that exists.

    Walks ``themes_dirs`` in order. The first parent that contains a
    sub-directory matching ``theme_slug`` wins. This means a downstream
    project's ``themes/default/`` shadows the FLS-package ``themes/default/``
    cleanly when downstream is listed first.

    Raises ``ImproperlyConfigured`` if no candidate exists. The exception
    message names the slug and the dirs searched so misconfiguration is
    obvious from the traceback.
    """
    for parent in themes_dirs:
        candidate = Path(parent) / theme_slug
        if candidate.is_dir():
            return candidate
    raise ImproperlyConfigured(
        f"FLS theme {theme_slug!r} not found in any of: {themes_dirs!r}"
    )


def configure_theme(
    *,
    theme_slug: str,
    themes_dirs: list[Path],
    templates: list[dict],
    staticfiles_dirs: list,
) -> Path:
    """Resolve the active theme and prepend its dirs to Django's settings.

    - Prepends ``<theme>/templates/`` to ``templates[0]["DIRS"]`` if it exists.
    - Prepends ``<theme>/static/`` to ``staticfiles_dirs`` if it exists.

    A Tier-1-only theme (token bundle, no templates) is valid; the missing
    sub-directories are silently skipped.

    Returns the resolved theme directory so callers can compute paths inside
    it (e.g. the email-colour parser pointing at ``theme.css``).
    """
    resolved = resolve_theme_dir(theme_slug, themes_dirs)
    templates_dir = resolved / "templates"
    static_dir = resolved / "static"
    if templates_dir.is_dir():
        templates[0].setdefault("DIRS", [])
        templates[0]["DIRS"].insert(0, str(templates_dir))
    if static_dir.is_dir():
        staticfiles_dirs.insert(0, static_dir)
    return resolved
