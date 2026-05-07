"""Tests for the theme resolver in ``freedom_ls.base.theming``.

Pure-filesystem logic: no DB, no test client. Uses ``tmp_path`` to fake themes
on disk so the tests are independent of whatever is actually shipped in
``freedom_ls/themes/``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from django.core.exceptions import ImproperlyConfigured

from freedom_ls.base.theming import configure_theme, resolve_theme_dir


def _make_theme(
    parent: Path, slug: str, *, with_templates: bool = False, with_static: bool = False
) -> Path:
    theme_dir = parent / slug
    theme_dir.mkdir(parents=True, exist_ok=True)
    if with_templates:
        (theme_dir / "templates").mkdir()
    if with_static:
        (theme_dir / "static").mkdir()
    return theme_dir


def test_resolve_theme_dir_returns_first_existing(tmp_path: Path) -> None:
    parent_a = tmp_path / "a"
    parent_b = tmp_path / "b"
    parent_a.mkdir()
    parent_b.mkdir()
    _make_theme(parent_b, "default")

    result = resolve_theme_dir("default", [parent_a, parent_b])

    assert result == parent_b / "default"


def test_resolve_theme_dir_downstream_takes_precedence(tmp_path: Path) -> None:
    """Downstream parent listed first must win even if FLS also ships the slug."""
    downstream = tmp_path / "downstream_themes"
    fls_pkg = tmp_path / "fls_pkg_themes"
    downstream.mkdir()
    fls_pkg.mkdir()
    _make_theme(downstream, "default")
    _make_theme(fls_pkg, "default")

    result = resolve_theme_dir("default", [downstream, fls_pkg])

    assert result == downstream / "default"


def test_resolve_theme_dir_raises_when_not_found(tmp_path: Path) -> None:
    parent = tmp_path / "themes"
    parent.mkdir()

    with pytest.raises(ImproperlyConfigured) as exc:
        resolve_theme_dir("missing", [parent])

    msg = str(exc.value)
    assert "missing" in msg
    assert str(parent) in msg


def test_resolve_theme_dir_walks_past_missing_parent(tmp_path: Path) -> None:
    """A parent dir that does not exist should not crash — fall through."""
    missing_parent = tmp_path / "does_not_exist"
    real_parent = tmp_path / "real"
    real_parent.mkdir()
    _make_theme(real_parent, "default")

    result = resolve_theme_dir("default", [missing_parent, real_parent])

    assert result == real_parent / "default"


def test_configure_theme_prepends_both_dirs(tmp_path: Path) -> None:
    parent = tmp_path / "themes"
    parent.mkdir()
    _make_theme(parent, "default", with_templates=True, with_static=True)

    templates: list[dict] = [{"DIRS": ["/existing/templates"]}]
    staticfiles_dirs: list[Path | str] = ["/existing/static"]

    resolved = configure_theme(
        theme_slug="default",
        themes_dirs=[parent],
        templates=templates,
        staticfiles_dirs=staticfiles_dirs,
    )

    assert resolved == parent / "default"
    assert templates[0]["DIRS"][0] == str(parent / "default" / "templates")
    assert templates[0]["DIRS"][1] == "/existing/templates"
    assert staticfiles_dirs[0] == parent / "default" / "static"
    assert staticfiles_dirs[1] == "/existing/static"


def test_configure_theme_skips_missing_subdirs(tmp_path: Path) -> None:
    """A Tier-1-only theme has no templates/ — must remain valid."""
    parent = tmp_path / "themes"
    parent.mkdir()
    _make_theme(parent, "tier1_only", with_templates=False, with_static=True)

    templates: list[dict] = [{"DIRS": []}]
    staticfiles_dirs: list[Path | str] = []

    resolved = configure_theme(
        theme_slug="tier1_only",
        themes_dirs=[parent],
        templates=templates,
        staticfiles_dirs=staticfiles_dirs,
    )

    assert resolved == parent / "tier1_only"
    assert templates[0]["DIRS"] == []
    assert staticfiles_dirs == [parent / "tier1_only" / "static"]


def test_configure_theme_no_static_no_templates(tmp_path: Path) -> None:
    parent = tmp_path / "themes"
    parent.mkdir()
    _make_theme(parent, "bare", with_templates=False, with_static=False)

    templates: list[dict] = [{"DIRS": []}]
    staticfiles_dirs: list[Path | str] = []

    configure_theme(
        theme_slug="bare",
        themes_dirs=[parent],
        templates=templates,
        staticfiles_dirs=staticfiles_dirs,
    )

    assert templates[0]["DIRS"] == []
    assert staticfiles_dirs == []


def test_configure_theme_exposes_inactive_themes_static_dirs(tmp_path: Path) -> None:
    """Inactive themes' static/ dirs must also land in STATICFILES_DIRS so
    ``/static/themes/<slug>/*`` resolves regardless of which theme is active.
    """
    parent = tmp_path / "themes"
    parent.mkdir()
    _make_theme(parent, "default", with_static=True)
    _make_theme(parent, "first_class", with_static=True)
    _make_theme(parent, "third", with_static=True)

    templates: list[dict] = [{"DIRS": []}]
    staticfiles_dirs: list[Path | str] = ["/existing/static"]

    configure_theme(
        theme_slug="first_class",
        themes_dirs=[parent],
        templates=templates,
        staticfiles_dirs=staticfiles_dirs,
    )

    assert staticfiles_dirs[0] == parent / "first_class" / "static"
    inactive_block = staticfiles_dirs[1:-1]
    assert set(inactive_block) == {
        parent / "default" / "static",
        parent / "third" / "static",
    }
    assert staticfiles_dirs[-1] == "/existing/static"


def test_configure_theme_does_not_duplicate_shadowed_slugs(tmp_path: Path) -> None:
    """If two parents both contain ``<slug>/static/``, only the first wins —
    matching ``resolve_theme_dir`` precedence.
    """
    downstream = tmp_path / "downstream"
    fls_pkg = tmp_path / "fls_pkg"
    downstream.mkdir()
    fls_pkg.mkdir()
    _make_theme(downstream, "default", with_static=True)
    _make_theme(fls_pkg, "default", with_static=True)

    templates: list[dict] = [{"DIRS": []}]
    staticfiles_dirs: list[Path | str] = []

    configure_theme(
        theme_slug="default",
        themes_dirs=[downstream, fls_pkg],
        templates=templates,
        staticfiles_dirs=staticfiles_dirs,
    )

    assert staticfiles_dirs == [downstream / "default" / "static"]


def test_configure_theme_inactive_theme_without_static_skipped(tmp_path: Path) -> None:
    """Inactive theme dirs without a static/ subdir are silently skipped."""
    parent = tmp_path / "themes"
    parent.mkdir()
    _make_theme(parent, "default", with_static=True)
    _make_theme(parent, "tier1_only", with_static=False)

    templates: list[dict] = [{"DIRS": []}]
    staticfiles_dirs: list[Path | str] = []

    configure_theme(
        theme_slug="default",
        themes_dirs=[parent],
        templates=templates,
        staticfiles_dirs=staticfiles_dirs,
    )

    assert staticfiles_dirs == [parent / "default" / "static"]


def test_configure_theme_initialises_dirs_when_missing(tmp_path: Path) -> None:
    """templates[0] without a DIRS key still works (setdefault)."""
    parent = tmp_path / "themes"
    parent.mkdir()
    _make_theme(parent, "t", with_templates=True)

    templates: list[dict] = [{}]
    staticfiles_dirs: list[Path | str] = []

    configure_theme(
        theme_slug="t",
        themes_dirs=[parent],
        templates=templates,
        staticfiles_dirs=staticfiles_dirs,
    )

    assert templates[0]["DIRS"] == [str(parent / "t" / "templates")]
