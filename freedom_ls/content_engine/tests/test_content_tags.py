"""Tests for template tags in content_tags.py.

Covers:
- admonition_config: type→registry entry resolution
- admonition_icon: renders SVG from a config dict
- c-admonition component: renders label, icon, body via markdown pipeline
"""

from __future__ import annotations

import pytest

from django.test import override_settings
from django.utils.safestring import SafeString

from freedom_ls.content_engine.templatetags.content_tags import (
    admonition_config,
    admonition_icon,
)
from freedom_ls.markdown_rendering.markdown_utils import render_markdown

# ---------------------------------------------------------------------------
# admonition_config
# ---------------------------------------------------------------------------


class TestAdmonitionConfig:
    """admonition_config returns the registry entry for a known type."""

    def test_known_type_returns_its_entry(self) -> None:
        result = admonition_config("note")

        assert result["label"] == "Note"
        assert result["icon"] == "info"
        assert result["color"] == "info"

    def test_known_type_tip_returns_tip_entry(self) -> None:
        result = admonition_config("tip")

        assert result["label"] == "Tip"
        assert result["color"] == "success"

    def test_unknown_type_returns_default_entry(self) -> None:
        result = admonition_config("completely_unknown_type")

        default = admonition_config("default")
        assert result == default

    def test_empty_string_type_returns_default_entry(self) -> None:
        result = admonition_config("")

        default = admonition_config("default")
        assert result == default

    @override_settings(
        ADMONITION_TYPES={
            "custom": {"label": "Custom Label", "icon": "star", "color": "success"},
            "default": {"label": "Fallback", "icon": "info", "color": "info"},
        }
    )
    def test_overridden_settings_are_respected(self) -> None:
        result = admonition_config("custom")

        assert result["label"] == "Custom Label"

    @override_settings(
        ADMONITION_TYPES={
            "custom": {"label": "Custom Label", "icon": "star", "color": "success"},
            "default": {"label": "Fallback", "icon": "info", "color": "info"},
        }
    )
    def test_unknown_type_falls_back_to_overridden_default(self) -> None:
        result = admonition_config("note")  # not in the override

        assert result["label"] == "Fallback"

    def test_returns_dict(self) -> None:
        result = admonition_config("warning")

        assert isinstance(result, dict)

    def test_all_builtin_types_resolve_without_error(self) -> None:
        builtin_types = [
            "note",
            "tip",
            "important",
            "warning",
            "danger",
            "key_takeaways",
            "checklist",
            "default",
        ]
        for admonition_type in builtin_types:
            result = admonition_config(admonition_type)
            assert isinstance(result, dict)
            assert "label" in result
            assert "icon" in result
            assert "color" in result


# ---------------------------------------------------------------------------
# admonition_icon
# ---------------------------------------------------------------------------


class TestAdmonitionIcon:
    """admonition_icon renders an SVG SafeString from a config dict."""

    def test_returns_safe_string(self) -> None:
        cfg = {"icon": "info", "color": "info"}
        result = admonition_icon(cfg)

        assert isinstance(result, SafeString)

    def test_result_contains_svg(self) -> None:
        cfg = {"icon": "info", "color": "info"}
        result = admonition_icon(cfg)

        assert "<svg" in result

    def test_empty_icon_in_cfg_falls_back_gracefully(self) -> None:
        cfg = {"icon": "", "color": "info"}
        result = admonition_icon(cfg)

        # Falls back to default_semantic="info" — should still produce SVG
        assert "<svg" in result
        assert isinstance(result, SafeString)

    def test_missing_icon_key_falls_back_gracefully(self) -> None:
        cfg = {"color": "info"}
        result = admonition_icon(cfg)

        assert "<svg" in result
        assert isinstance(result, SafeString)

    def test_custom_css_class_is_accepted(self) -> None:
        cfg = {"icon": "info"}
        result = admonition_icon(cfg, css_class="size-6")

        assert isinstance(result, SafeString)


# ---------------------------------------------------------------------------
# c-admonition component (via markdown pipeline)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAdmonitionComponent:
    """c-admonition renders through the full markdown pipeline."""

    @pytest.fixture
    def request_(self, site_aware_request):
        return site_aware_request.get("/")

    def test_known_type_renders_label_from_registry(self, request_) -> None:
        result = render_markdown(
            '<c-admonition type="note">Body text</c-admonition>', request_
        )

        # The "Note" label from the registry must appear in the output
        assert "Note" in result

    def test_explicit_title_overrides_registry_label(self, request_) -> None:
        result = render_markdown(
            '<c-admonition type="note" title="My Custom Title">Content</c-admonition>',
            request_,
        )

        assert "My Custom Title" in result

    def test_body_text_appears_in_output(self, request_) -> None:
        result = render_markdown(
            '<c-admonition type="tip">Important body content</c-admonition>', request_
        )

        assert "Important body content" in result

    def test_body_markdown_is_processed(self, request_) -> None:
        result = render_markdown(
            '<c-admonition type="note">This is **bold** text</c-admonition>',
            request_,
        )

        assert "<strong>bold</strong>" in result

    def test_icon_svg_is_rendered(self, request_) -> None:
        result = render_markdown(
            '<c-admonition type="note">Content</c-admonition>', request_
        )

        assert "<svg" in result

    def test_unknown_type_falls_back_to_default_without_error(self, request_) -> None:
        result = render_markdown(
            '<c-admonition type="completely_unknown">Content</c-admonition>', request_
        )

        # Should not raise; body text must survive
        assert "Content" in result

    def test_returns_safe_string(self, request_) -> None:
        result = render_markdown(
            '<c-admonition type="note">Content</c-admonition>', request_
        )

        assert isinstance(result, SafeString)

    def test_cotton_tag_not_in_output(self, request_) -> None:
        result = render_markdown(
            '<c-admonition type="note">Content</c-admonition>', request_
        )

        assert "<c-admonition" not in result

    def test_tip_type_renders_tip_label(self, request_) -> None:
        """type="tip" renders the "Tip" label from the registry."""
        result = render_markdown(
            '<c-admonition type="tip">Tip content</c-admonition>', request_
        )

        assert "Tip" in result
        assert "Tip content" in result

    def test_warning_type_renders_warning_label(self, request_) -> None:
        """type="warning" renders the "Warning" label from the registry."""
        result = render_markdown(
            '<c-admonition type="warning">Warning content</c-admonition>', request_
        )

        assert "Warning" in result
        assert "Warning content" in result

    def test_danger_type_renders_danger_label(self, request_) -> None:
        """type="danger" renders the "Danger" label from the registry."""
        result = render_markdown(
            '<c-admonition type="danger">Danger content</c-admonition>', request_
        )

        assert "Danger" in result
        assert "Danger content" in result

    def test_admonition_has_role_note_for_accessibility(self, request_) -> None:
        """Admonition renders with role="note" for screen reader accessibility."""
        result = render_markdown(
            '<c-admonition type="note">Note content</c-admonition>', request_
        )

        assert 'role="note"' in result

    def test_admonition_has_aria_labelledby(self, request_) -> None:
        """Admonition renders with aria-labelledby linking the heading to the container."""
        result = render_markdown(
            '<c-admonition type="note">Content</c-admonition>', request_
        )

        assert "aria-labelledby" in result
