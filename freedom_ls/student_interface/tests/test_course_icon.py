"""Tests for the course-icon resolver."""

from __future__ import annotations

from typing import Any

import pytest

from django.test import override_settings
from django.utils.safestring import SafeString

from freedom_ls.icons.backend import get_icon_backend
from freedom_ls.icons.loader import load_iconify_data
from freedom_ls.student_interface.course_icon import (
    IconResolutionError,
    render_course_icon,
)


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
        "freedom_ls.student_interface.course_icon.load_iconify_data",
        fake_loader,
    )
    monkeypatch.setattr(
        "freedom_ls.icons.backend.load_iconify_data",
        fake_loader,
    )


def test_empty_icon_renders_default_course_semantic() -> None:
    out = render_course_icon("")
    assert isinstance(out, SafeString)
    assert "<svg" in out
    assert 'aria-label="course"' in out


def test_semantic_name_renders_via_backend_and_ignores_fallback() -> None:
    out = render_course_icon("notes", "phosphor:drone")
    assert isinstance(out, SafeString)
    # The notes semantic resolves on every set; the fallback is unused.
    assert "<svg" in out


def test_safe_string_returned() -> None:
    assert isinstance(render_course_icon(""), SafeString)


def test_literal_glyph_in_active_set(monkeypatch: pytest.MonkeyPatch) -> None:
    # Active set is heroicons by default; pretend it has a 'drone' glyph.
    real_data = load_iconify_data("heroicons")
    fake_heroicons = {
        "icons": {
            **real_data["icons"],
            "drone": {"body": "<path d='M0 0'/>"},
            "drone-solid": {"body": "<path d='M0 0'/>"},
            "drone-20-solid": {"body": "<path d='M0 0'/>"},
            "drone-16-solid": {"body": "<path d='M0 0'/>"},
        },
        "width": 24,
        "height": 24,
    }
    _stub_iconify(monkeypatch, {"heroicons": fake_heroicons})

    out = render_course_icon("drone")
    assert "<svg" in out
    assert 'aria-label="drone"' in out


def test_explicit_fallback_used_when_active_lacks_glyph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_heroicons = load_iconify_data("heroicons")
    real_phosphor = load_iconify_data("phosphor")
    # Active set (heroicons) does NOT have drone; phosphor does.
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

    out = render_course_icon("drone", "phosphor:drone")
    assert "<svg" in out
    assert 'aria-label="drone"' in out


def test_unknown_icon_with_no_fallback_renders_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out = render_course_icon("zzz_no_such_glyph", "")
    assert "<svg" in out
    assert 'aria-label="course"' in out


def test_unknown_icon_with_malformed_fallback_renders_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out = render_course_icon("zzz_no_such_glyph", "bogus:")
    assert "<svg" in out
    assert 'aria-label="course"' in out


def test_unknown_iconset_in_fallback_renders_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out = render_course_icon("zzz_no_such_glyph", "made_up_set:foo")
    assert "<svg" in out
    assert 'aria-label="course"' in out


def test_missing_suffixed_glyph_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    # Heroicons has 4 variants; mini suffix is "-20-solid". Provide the base
    # glyph and the outline (no suffix) but NOT the solid variant — asking for
    # the solid variant should raise.
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
        render_course_icon("halfshipped", variant="solid")


@override_settings(FREEDOM_LS_ICON_SET="lucide")
def test_active_set_respects_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    real_lucide = load_iconify_data("lucide")
    fake_lucide = {
        "icons": {
            **real_lucide["icons"],
            "drone": {"body": "<path d='M2 2'/>"},
        },
        "width": 24,
        "height": 24,
    }
    _stub_iconify(monkeypatch, {"lucide": fake_lucide})

    out = render_course_icon("drone")
    assert "<svg" in out
