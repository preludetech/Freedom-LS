"""Tests for ``validate_course_icon_fields`` and the Course icon round-trip."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from django.core.exceptions import ValidationError

from freedom_ls.content_engine.icon_validation import validate_course_icon_fields
from freedom_ls.content_engine.management.commands.content_save import (
    save_content_to_db,
)
from freedom_ls.content_engine.models import Course
from freedom_ls.icons.loader import load_iconify_data

# --- pure unit tests ---


def test_both_empty_is_ok() -> None:
    validate_course_icon_fields("", "")


def test_empty_icon_with_fallback_raises() -> None:
    with pytest.raises(ValidationError):
        validate_course_icon_fields("", "phosphor:drone")


def test_semantic_name_alone_is_ok() -> None:
    validate_course_icon_fields("notes", "")


def test_semantic_name_plus_valid_fallback_is_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_phosphor = load_iconify_data("phosphor")
    fake_phosphor = {
        "icons": {
            **real_phosphor["icons"],
            "drone": {"body": "<path d='M0 0'/>"},
            "drone-fill": {"body": "<path d='M0 0'/>"},
            "drone-bold": {"body": "<path d='M0 0'/>"},
            "drone-light": {"body": "<path d='M0 0'/>"},
            "drone-thin": {"body": "<path d='M0 0'/>"},
        },
        "width": 24,
        "height": 24,
    }

    def fake_loader(set_name: str):
        if set_name == "phosphor":
            return fake_phosphor
        return load_iconify_data(set_name)

    monkeypatch.setattr(
        "freedom_ls.content_engine.icon_validation.load_iconify_data",
        fake_loader,
    )

    validate_course_icon_fields("notes", "phosphor:drone")


def test_unknown_literal_glyph_raises() -> None:
    with pytest.raises(ValidationError):
        validate_course_icon_fields("xx_zzz_definitely_not_a_glyph_xx", "")


def test_literal_glyph_present_in_at_least_one_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If at least one set has the unsuffixed glyph (and all variants), accept."""
    fake_glyph = "fakeglyph_for_testing"

    def fake_loader(set_name: str):
        real = load_iconify_data(set_name)
        if set_name == "heroicons":
            return {
                "icons": {
                    **real["icons"],
                    fake_glyph: {"body": "<path d='M0 0'/>"},
                    f"{fake_glyph}-solid": {"body": "<path d='M0 0'/>"},
                    f"{fake_glyph}-20-solid": {"body": "<path d='M0 0'/>"},
                    f"{fake_glyph}-16-solid": {"body": "<path d='M0 0'/>"},
                },
                "width": 24,
                "height": 24,
            }
        return real

    monkeypatch.setattr(
        "freedom_ls.content_engine.icon_validation.load_iconify_data",
        fake_loader,
    )

    validate_course_icon_fields(fake_glyph, "")


def test_variant_pairing_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """If a set has the unsuffixed glyph but lacks a required variant, raise."""
    real = load_iconify_data("heroicons")
    # Heroicons requires solid, mini and micro variants.
    fake_heroicons = {
        "icons": {
            **real["icons"],
            "halfshipped": {"body": "<path d='M0 0'/>"},
            # MISSING: halfshipped-solid, etc.
        },
        "width": 24,
        "height": 24,
    }

    def fake_loader(set_name: str):
        if set_name == "heroicons":
            return fake_heroicons
        return load_iconify_data(set_name)

    monkeypatch.setattr(
        "freedom_ls.content_engine.icon_validation.load_iconify_data",
        fake_loader,
    )

    with pytest.raises(ValidationError) as excinfo:
        validate_course_icon_fields("halfshipped", "")
    assert "variant" in str(excinfo.value).lower()


def test_malformed_fallback_raises() -> None:
    with pytest.raises(ValidationError):
        validate_course_icon_fields("notes", "  phosphor:drone   ".strip() + "::")


def test_fallback_with_unknown_set_raises() -> None:
    with pytest.raises(ValidationError):
        validate_course_icon_fields("notes", "made_up_set:foo")


def test_fallback_glyph_missing_in_set_raises() -> None:
    with pytest.raises(ValidationError):
        validate_course_icon_fields("notes", "phosphor:zzz_no_such_glyph_in_phosphor")


def test_whitespace_only_icon_treated_as_empty() -> None:
    # "   " trims to "". Fallback set without icon raises.
    with pytest.raises(ValidationError):
        validate_course_icon_fields("   ", "phosphor:drone")


# --- integration: content_save round-trip ---


@pytest.mark.django_db
def test_content_save_persists_icon_and_fallback(site, mock_site_context):
    """A course frontmatter with `icon: notes` round-trips into Course.icon."""
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "iconned_course"
        course_dir.mkdir()

        (course_dir / "course.md").write_text(
            """---
content_type: COURSE
title: Iconned Course
description: Has an icon
icon: notes
uuid: 00000000-0000-0000-0000-000000000010
---

Body
"""
        )

        # A trivial child so the directory is valid.
        (course_dir / "1. topic.md").write_text(
            """---
content_type: TOPIC
title: A Topic
uuid: 00000000-0000-0000-0000-000000000011
---

Hello
"""
        )

        save_content_to_db(course_dir, site.name)

        course = Course.objects.get(title="Iconned Course", site=site)
        assert course.icon == "notes"
        assert course.icon_fallback == ""


@pytest.mark.django_db
def test_content_save_rejects_invalid_icon(site, mock_site_context):
    """Saving a course with an unrecognised literal glyph raises."""
    with tempfile.TemporaryDirectory() as tmpdir:
        course_dir = Path(tmpdir) / "bad_icon_course"
        course_dir.mkdir()

        (course_dir / "course.md").write_text(
            """---
content_type: COURSE
title: Bad Icon Course
description: Has an icon
icon: xx_zzz_definitely_not_a_glyph_xx
uuid: 00000000-0000-0000-0000-000000000020
---

Body
"""
        )

        (course_dir / "1. topic.md").write_text(
            """---
content_type: TOPIC
title: A Topic
uuid: 00000000-0000-0000-0000-000000000021
---

Hello
"""
        )

        with pytest.raises((ValidationError, ValueError)):
            save_content_to_db(course_dir, site.name)
