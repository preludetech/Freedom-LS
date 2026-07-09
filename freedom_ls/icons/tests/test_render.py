"""Tests for the generic icon resolver (freedom_ls.icons.render)."""

from __future__ import annotations

from typing import Any

import pytest

from django.test import override_settings
from django.utils.safestring import SafeString

from freedom_ls.icons.backend import get_icon_backend
from freedom_ls.icons.loader import load_iconify_data
from freedom_ls.icons.render import IconResolutionError, render_icon


@pytest.fixture(autouse=True)
def _clear_icon_backend_cache():
    """Reset the cached icon backend so override_settings is honoured."""
    get_icon_backend.cache_clear()
    yield
    get_icon_backend.cache_clear()


def _stub_iconify(monkeypatch: pytest.MonkeyPatch, datasets: dict[str, dict[str, Any]]):
    """Replace ``load_iconify_data`` with an in-memory map.

    ``datasets`` is keyed by set name; values look like an iconify JSON file
    (``{"icons": {...}, "width": 24, "height": 24}``).
    """

    def fake_loader(set_name: str):
        if set_name not in datasets:
            raise ValueError(f"unknown set {set_name!r}")
        return datasets[set_name]

    monkeypatch.setattr(
        "freedom_ls.icons.render.load_iconify_data",
        fake_loader,
    )
    monkeypatch.setattr(
        "freedom_ls.icons.backend.load_iconify_data",
        fake_loader,
    )


# ---- Step 1: empty icon -> default_semantic ----


@pytest.mark.parametrize("default_semantic", ["course", "info"])
def test_empty_icon_resolves_to_default_semantic(default_semantic: str) -> None:
    out = render_icon("", default_semantic=default_semantic)
    assert isinstance(out, SafeString)
    assert "<svg" in out
    assert f'aria-label="{default_semantic}"' in out


# ---- Step 2: semantic name ----


@pytest.mark.parametrize(
    ("semantic_name", "default_semantic"),
    [
        ("notes", "course"),
        ("info", "course"),
        ("success", "info"),
    ],
)
def test_semantic_name_resolves_correctly(
    semantic_name: str, default_semantic: str
) -> None:
    out = render_icon(semantic_name, default_semantic=default_semantic)
    assert isinstance(out, SafeString)
    assert "<svg" in out
    assert f'aria-label="{semantic_name}"' in out


# ---- Step 3: literal glyph in the active set ----


@override_settings(FREEDOM_LS_ICON_SET="heroicons")
def test_literal_glyph_in_active_set_resolves(monkeypatch: pytest.MonkeyPatch) -> None:
    real_data = load_iconify_data("heroicons")
    fake_heroicons = {
        "icons": {
            **real_data["icons"],
            "widget": {"body": "<path d='M0 0'/>"},
            "widget-solid": {"body": "<path d='M0 0'/>"},
            "widget-20-solid": {"body": "<path d='M0 0'/>"},
            "widget-16-solid": {"body": "<path d='M0 0'/>"},
        },
        "width": 24,
        "height": 24,
    }
    _stub_iconify(monkeypatch, {"heroicons": fake_heroicons})

    out = render_icon("widget", default_semantic="course")
    assert isinstance(out, SafeString)
    assert "<svg" in out
    assert 'aria-label="widget"' in out


@override_settings(FREEDOM_LS_ICON_SET="heroicons")
@pytest.mark.parametrize("default_semantic", ["course", "info"])
def test_literal_glyph_in_active_set_uses_parametrised_default_semantic(
    monkeypatch: pytest.MonkeyPatch,
    default_semantic: str,
) -> None:
    """Parametrised default_semantic doesn't affect literal glyph resolution."""
    real_data = load_iconify_data("heroicons")
    fake_heroicons = {
        "icons": {
            **real_data["icons"],
            "widget": {"body": "<path d='M0 0'/>"},
            "widget-solid": {"body": "<path d='M0 0'/>"},
            "widget-20-solid": {"body": "<path d='M0 0'/>"},
            "widget-16-solid": {"body": "<path d='M0 0'/>"},
        },
        "width": 24,
        "height": 24,
    }
    _stub_iconify(monkeypatch, {"heroicons": fake_heroicons})

    out = render_icon("widget", default_semantic=default_semantic)
    assert "<svg" in out
    assert 'aria-label="widget"' in out


# ---- Step 4: <iconset>:<glyph> fallback when literal is absent from active set ----


@override_settings(FREEDOM_LS_ICON_SET="heroicons")
def test_iconset_colon_glyph_fallback_used_when_active_lacks_glyph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_heroicons = load_iconify_data("heroicons")
    real_phosphor = load_iconify_data("phosphor")
    # Active set (heroicons) does NOT have 'drone'; phosphor does.
    fake_heroicons = {
        "icons": dict(real_heroicons["icons"]),
        "width": 24,
        "height": 24,
    }
    fake_phosphor = {
        "icons": {
            **real_phosphor["icons"],
            "drone": {"body": "<path d='M1 1'/>"},
            "drone-fill": {"body": "<path d='M1 1'/>"},
            "drone-bold": {"body": "<path d='M1 1'/>"},
            "drone-light": {"body": "<path d='M1 1'/>"},
            "drone-thin": {"body": "<path d='M1 1'/>"},
        },
        "width": 24,
        "height": 24,
    }
    _stub_iconify(
        monkeypatch,
        {"heroicons": fake_heroicons, "phosphor": fake_phosphor},
    )

    out = render_icon("drone", "phosphor:drone", default_semantic="course")
    assert isinstance(out, SafeString)
    assert "<svg" in out
    assert 'aria-label="drone"' in out


@override_settings(FREEDOM_LS_ICON_SET="heroicons")
@pytest.mark.parametrize("default_semantic", ["course", "info"])
def test_iconset_glyph_fallback_uses_parametrised_default_semantic_not_glyph(
    monkeypatch: pytest.MonkeyPatch,
    default_semantic: str,
) -> None:
    """Fallback resolves the glyph, not the default_semantic."""
    real_heroicons = load_iconify_data("heroicons")
    real_phosphor = load_iconify_data("phosphor")
    fake_heroicons = {
        "icons": dict(real_heroicons["icons"]),
        "width": 24,
        "height": 24,
    }
    fake_phosphor = {
        "icons": {
            **real_phosphor["icons"],
            "drone": {"body": "<path d='M1 1'/>"},
            "drone-fill": {"body": "<path d='M1 1'/>"},
            "drone-bold": {"body": "<path d='M1 1'/>"},
            "drone-light": {"body": "<path d='M1 1'/>"},
            "drone-thin": {"body": "<path d='M1 1'/>"},
        },
        "width": 24,
        "height": 24,
    }
    _stub_iconify(
        monkeypatch,
        {"heroicons": fake_heroicons, "phosphor": fake_phosphor},
    )

    out = render_icon("drone", "phosphor:drone", default_semantic=default_semantic)
    assert "<svg" in out
    # The aria-label should be the glyph name, not the default_semantic
    assert 'aria-label="drone"' in out


# ---- Step 5: graceful fallback to default_semantic when nothing resolves ----


@pytest.mark.parametrize("default_semantic", ["course", "info"])
def test_unknown_icon_renders_default_semantic(default_semantic: str) -> None:
    out = render_icon("zzz_no_such_glyph", "", default_semantic=default_semantic)
    assert isinstance(out, SafeString)
    assert "<svg" in out
    assert f'aria-label="{default_semantic}"' in out


@pytest.mark.parametrize("default_semantic", ["course", "info"])
def test_malformed_fallback_renders_default_semantic(default_semantic: str) -> None:
    out = render_icon("zzz_no_such_glyph", "bogus:", default_semantic=default_semantic)
    assert isinstance(out, SafeString)
    assert "<svg" in out
    assert f'aria-label="{default_semantic}"' in out


@pytest.mark.parametrize("default_semantic", ["course", "info"])
def test_unknown_iconset_in_fallback_renders_default_semantic(
    default_semantic: str,
) -> None:
    out = render_icon(
        "zzz_no_such_glyph", "made_up_set:foo", default_semantic=default_semantic
    )
    assert isinstance(out, SafeString)
    assert "<svg" in out
    assert f'aria-label="{default_semantic}"' in out


def test_render_icon_never_raises_for_unknown_icon() -> None:
    """render_icon must not raise for any unrecognised icon string."""
    out = render_icon("definitely_not_real_xyz", default_semantic="course")
    assert "<svg" in out


# ---- Raise paths: half-shipped icon set and unsupported variant ----


@override_settings(FREEDOM_LS_ICON_SET="heroicons")
def test_missing_suffixed_glyph_raises_icon_resolution_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """IconResolutionError is raised when the base glyph exists but the suffixed variant does not."""
    real = load_iconify_data("heroicons")
    fake = {
        "icons": {
            **real["icons"],
            "halfshipped": {"body": "<path d='M0 0'/>"},
            # Missing: halfshipped-solid, -20-solid, -16-solid
        },
        "width": 24,
        "height": 24,
    }
    _stub_iconify(monkeypatch, {"heroicons": fake})

    with pytest.raises(IconResolutionError):
        render_icon("halfshipped", default_semantic="course", variant="solid")


@override_settings(FREEDOM_LS_ICON_SET="heroicons")
def test_unsupported_variant_raises_value_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ValueError is raised when an unrecognised variant is requested for the active set."""
    real = load_iconify_data("heroicons")
    fake_heroicons = {
        "icons": {
            **real["icons"],
            "widget": {"body": "<path d='M0 0'/>"},
        },
        "width": 24,
        "height": 24,
    }
    _stub_iconify(monkeypatch, {"heroicons": fake_heroicons})

    with pytest.raises(ValueError, match="not supported"):
        render_icon(
            "widget", default_semantic="course", variant="completely_unknown_variant"
        )
