"""Tests for the icon_from_name filter and <c-icon /> cotton component."""

import re

import pytest
from django_cotton.compiler_regex import CottonCompiler

from django.template import Context, Template

from freedom_ls.base.icons import ICONS
from freedom_ls.base.templatetags.icon_tags import icon_from_name


class TestIconNameFilter:
    """Tests for the icon_from_name template filter."""

    def test_resolves_semantic_name(self) -> None:
        assert icon_from_name("next")

    def test_unknown_name_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            icon_from_name("nonexistent_icon_xyz")

    def test_force_bypasses_registry(self) -> None:
        result = icon_from_name("arrow-right", force="true")
        assert result == "arrow-right"

    def test_force_with_yes(self) -> None:
        result = icon_from_name("some-icon", force="yes")
        assert result == "some-icon"

    def test_force_with_1(self) -> None:
        result = icon_from_name("some-icon", force="1")
        assert result == "some-icon"

    def test_force_false_uses_registry(self) -> None:
        result = icon_from_name("next", force="false")
        assert result == "arrow-right"


class TestIconRegistryValidation:
    """Test that every value in ICONS maps to a valid heroicon."""

    def test_all_registry_values_are_valid_heroicons(self) -> None:
        from heroicons import _load_icon

        for semantic_name, heroicon_from_name in ICONS.items():
            try:
                _load_icon("outline", heroicon_from_name)
            except Exception as e:
                pytest.fail(
                    f"ICONS[{semantic_name!r}] = {heroicon_from_name!r} is not a valid heroicon: {e}"
                )


_cotton_compiler = CottonCompiler()


class TestIconCottonComponent:
    """Tests for the <c-icon /> cotton component."""

    def _render(self, template_string: str) -> str:
        """Render a template string containing a cotton component.

        Uses the CottonCompiler to preprocess <c-icon /> tags into
        Django template tags before rendering.
        """
        processed = _cotton_compiler.process(template_string)
        t = Template(processed)
        return t.render(Context())

    def test_renders_svg_element(self) -> None:
        result = self._render('<c-icon name="next" />')
        assert "<svg" in result
        assert "</svg>" in result

    def test_default_class_is_size_5(self) -> None:
        result = self._render('<c-icon name="next" />')
        assert 'class="size-5"' in result

    def test_default_role_is_img(self) -> None:
        result = self._render('<c-icon name="next" />')
        assert 'role="img"' in result

    def test_default_aria_label_is_semantic_name(self) -> None:
        result = self._render('<c-icon name="next" />')
        assert 'aria-label="next"' in result

    def test_custom_aria_label(self) -> None:
        result = self._render('<c-icon name="success" aria_label="Done" />')
        assert 'aria-label="Done"' in result

    def test_solid_variant(self) -> None:
        outline_result = self._render('<c-icon name="next" />')
        solid_result = self._render('<c-icon name="next" variant="solid" />')
        assert "<svg" in solid_result
        assert outline_result != solid_result

    def test_custom_class(self) -> None:
        result = self._render('<c-icon name="next" class="size-6 text-red-500" />')
        assert 'class="size-6 text-red-500"' in result

    def test_force_bypass(self) -> None:
        result = self._render('<c-icon name="arrow-right" force="true" />')
        assert "<svg" in result

    def test_force_equivalence(self) -> None:
        """Registry lookup and force bypass should render the same SVG paths."""
        registry_result = self._render('<c-icon name="next" />')
        force_result = self._render('<c-icon name="arrow-right" force="true" />')
        registry_paths = sorted(re.findall(r'd="([^"]+)"', registry_result))
        force_paths = sorted(re.findall(r'd="([^"]+)"', force_result))
        assert registry_paths == force_paths
        assert len(registry_paths) > 0
