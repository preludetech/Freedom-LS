"""Tests for the icon template tag."""

import re

import pytest

from django.template import Context, Template


class TestIconTemplateTag:
    """Tests for the {% icon %} template tag."""

    def _render(self, template_string: str) -> str:
        """Render a template string and return the result."""
        t = Template("{% load icon_tags %}" + template_string)
        return t.render(Context())

    def test_renders_svg_element(self) -> None:
        result = self._render('{% icon "next" %}')
        assert "<svg" in result
        assert "</svg>" in result

    def test_registry_and_force_render_same_icon(self) -> None:
        """{% icon "next" %} and {% icon "arrow-right" force=True %} should
        render the same heroicon SVG path data."""
        registry_result = self._render('{% icon "next" %}')
        force_result = self._render('{% icon "arrow-right" force=True %}')
        # Extract path d= attributes - they should match
        assert "path" in registry_result
        assert "path" in force_result
        # Both should contain the same path data
        registry_paths = sorted(re.findall(r'd="([^"]+)"', registry_result))
        force_paths = sorted(re.findall(r'd="([^"]+)"', force_result))
        assert registry_paths == force_paths
        assert len(registry_paths) > 0

    def test_solid_variant_differs_from_outline(self) -> None:
        outline_result = self._render('{% icon "next" %}')
        solid_result = self._render('{% icon "next" variant="solid" %}')
        assert "<svg" in outline_result
        assert "<svg" in solid_result
        assert outline_result != solid_result

    def test_default_aria_hidden(self) -> None:
        result = self._render('{% icon "next" %}')
        assert 'aria-hidden="true"' in result

    def test_aria_label_renders_role_and_title(self) -> None:
        result = self._render('{% icon "next" aria_label="Close" %}')
        assert 'role="img"' in result
        assert "<title" in result
        assert "Close</title>" in result
        assert "aria-hidden" not in result

    def test_unknown_name_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            self._render('{% icon "nonexistent_icon_xyz" %}')

    def test_force_bypasses_registry(self) -> None:
        # This should not raise even though "arrow-right" is not a registry key
        result = self._render('{% icon "arrow-right" force=True %}')
        assert "<svg" in result

    def test_default_class_is_size_5(self) -> None:
        result = self._render('{% icon "next" %}')
        assert 'class="size-5"' in result

    def test_custom_class_is_applied(self) -> None:
        result = self._render('{% icon "next" class="size-6 text-red-500" %}')
        assert 'class="size-6 text-red-500"' in result
        assert 'class="size-5"' not in result

    def test_force_with_invalid_heroicon_raises_error(self) -> None:
        from heroicons import IconDoesNotExist

        with pytest.raises(IconDoesNotExist):
            self._render('{% icon "not-a-real-heroicon" force=True %}')
