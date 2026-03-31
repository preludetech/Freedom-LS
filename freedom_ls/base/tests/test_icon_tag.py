"""Tests for the <c-icon /> cotton component."""

from django_cotton.compiler_regex import CottonCompiler

from django.template import Context, Template

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
        assert 'class="inline size-5"' in result

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
        assert 'class="inline size-6 text-red-500"' in result
