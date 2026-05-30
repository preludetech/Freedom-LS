"""Tests for the <c-dropdown-menu /> cotton component."""

from django_cotton.compiler_regex import CottonCompiler

from django.template import Context, Template

_cotton_compiler = CottonCompiler()


class TestDropdownMenuComponent:
    """Rendering behaviour of <c-dropdown-menu />."""

    def _render(self, template_string: str) -> str:
        processed = _cotton_compiler.process(template_string)
        t = Template(processed)
        return t.render(Context())

    def test_authoring_comments_do_not_leak_into_output(self) -> None:
        """Internal authoring comments must not reach the rendered HTML."""
        result = self._render(
            "<c-dropdown-menu><c-button dropdown='true'>Item</c-button></c-dropdown-menu>"
        )
        assert "3-dots menu button" not in result
        assert "Dropdown menu" not in result
        assert "<!--" not in result
