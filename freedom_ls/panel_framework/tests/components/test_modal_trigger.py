"""Tests for the <c-modal-trigger /> cotton component."""

from freedom_ls.panel_framework.tests.cotton_helpers import render_cotton


class TestModalTriggerSize:
    """<c-modal-trigger /> passes size and class through to its button."""

    def test_size_small_and_class_reach_the_button(self) -> None:
        result = render_cotton(
            '<c-modal-trigger url="/x" label="Go" size="small" class="extra" />'
        )
        assert "panel-btn-sm" in result
        assert "extra" in result

    def test_without_a_size_the_button_is_full_size(self) -> None:
        result = render_cotton('<c-modal-trigger url="/x" label="Go" />')
        assert "panel-btn-sm" not in result


class TestModalTriggerAttributes:
    """<c-modal-trigger /> forwards attributes it has no prop for."""

    def test_a_data_attribute_reaches_the_button(self) -> None:
        result = render_cotton(
            '<c-modal-trigger url="/x" label="Go" data-entry-pk="7" />'
        )
        assert 'data-entry-pk="7"' in result
