"""Tests for the <c-button /> cotton component's loading prop."""

from django_cotton.compiler_regex import CottonCompiler

from django.template import Context, Template

_cotton_compiler = CottonCompiler()

# The two loading states are driven from the `.htmx-request` class HTMX puts on
# the ancestor that triggered the request, reached with a descendant variant on
# each span.
IDLE_STATE = "[.htmx-request_&]:hidden"
BUSY_STATE = "[.htmx-request_&]:inline-flex"


class TestButtonLoadingProp:
    """Tests for the loading indicator behavior of <c-button />."""

    def _render(self, template_string: str) -> str:
        processed = _cotton_compiler.process(template_string)
        t = Template(processed)
        return t.render(Context())

    def test_loading_false_renders_normal_button(self) -> None:
        result = self._render("<c-button>Save</c-button>")
        assert IDLE_STATE not in result
        assert BUSY_STATE not in result
        assert "Save" in result

    def test_loading_true_renders_both_states(self) -> None:
        result = self._render('<c-button loading="true">Save</c-button>')
        assert IDLE_STATE in result
        assert BUSY_STATE in result

    def test_loading_default_text_shows_default_loading_text(self) -> None:
        result = self._render('<c-button loading="true">Save</c-button>')
        assert "Saving..." in result

    def test_loading_custom_text(self) -> None:
        result = self._render(
            '<c-button loading="true" loading_text="Deleting...">Delete</c-button>'
        )
        assert "Deleting..." in result

    def test_loading_shows_spinner_icon(self) -> None:
        result = self._render('<c-button loading="true">Save</c-button>')
        assert "animate-spin" in result

    def test_loading_preserves_normal_content(self) -> None:
        result = self._render('<c-button loading="true">Save</c-button>')
        assert "Save" in result

    def test_loading_with_icon_left(self) -> None:
        result = self._render(
            '<c-button loading="true" icon_left="check">Save</c-button>'
        )
        assert IDLE_STATE in result
        assert BUSY_STATE in result

    def test_dropdown_button_does_not_have_loading(self) -> None:
        """Loading prop only applies to standard buttons, not dropdown items."""
        result = self._render(
            '<c-button dropdown="true" loading="true">Item</c-button>'
        )
        assert IDLE_STATE not in result
        assert "Item" in result
