"""Tests for the icon template tag."""

import pytest

from django.template import Context, Template


class TestIconTemplateTag:
    """Tests for the {% icon %} template tag."""

    def _render(self, template_string: str) -> str:
        t = Template(template_string)
        return t.render(Context())

    def test_basic_rendering(self) -> None:
        result = self._render('{% load icon_tags %}{% icon "success" %}')
        assert "<svg" in result
        assert "</svg>" in result

    def test_with_variant(self) -> None:
        outline = self._render('{% load icon_tags %}{% icon "success" %}')
        solid = self._render('{% load icon_tags %}{% icon "success" variant="solid" %}')
        assert outline != solid

    def test_with_css_class(self) -> None:
        result = self._render(
            '{% load icon_tags %}{% icon "success" css_class="size-6 text-green-500" %}'
        )
        assert 'class="inline size-6 text-green-500"' in result

    def test_with_aria_label(self) -> None:
        result = self._render(
            '{% load icon_tags %}{% icon "success" aria_label="Done" %}'
        )
        assert 'aria-label="Done"' in result

    def test_unknown_name_raises(self) -> None:
        with pytest.raises(KeyError):
            self._render('{% load icon_tags %}{% icon "nonexistent_xyz" %}')

    def test_output_is_safe_html(self) -> None:
        result = self._render('{% load icon_tags %}{% icon "success" %}')
        # If the output were auto-escaped, we'd see &lt;svg instead of <svg
        assert "<svg" in result
        assert "&lt;svg" not in result
