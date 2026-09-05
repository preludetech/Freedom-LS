"""Tests for the shared <c-error-page /> cotton component."""

import re

import pytest
from django_cotton.compiler_regex import CottonCompiler

from django.template import Context, Template

_cotton_compiler = CottonCompiler()


def _render(template_string: str) -> str:
    processed = _cotton_compiler.process(template_string)
    t = Template(processed)
    return t.render(Context())


class TestErrorPageComponent:
    """Tests for the status mark, heading and slot content of <c-error-page />."""

    def test_shows_status_label(self) -> None:
        result = _render(
            '<c-error-page status="404" heading="We cannot find that page">'
            "<p>Body</p></c-error-page>"
        )
        assert "404" in result

    def test_shows_heading_text(self) -> None:
        result = _render(
            '<c-error-page status="404" heading="We cannot find that page">'
            "<p>Body</p></c-error-page>"
        )
        assert "We cannot find that page" in result

    def test_renders_exactly_one_h1(self) -> None:
        result = _render(
            '<c-error-page status="404" heading="We cannot find that page">'
            "<p>Body</p></c-error-page>"
        )
        assert len(re.findall(r"<h1[ >]", result)) == 1

    def test_heading_is_wrapped_in_h1(self) -> None:
        result = _render(
            '<c-error-page status="404" heading="We cannot find that page">'
            "<p>Body</p></c-error-page>"
        )
        assert re.search(r"<h1[^>]*>\s*We cannot find that page\s*</h1>", result)

    def test_status_mark_is_hidden_from_assistive_technology(self) -> None:
        result = _render(
            '<c-error-page status="404" heading="We cannot find that page">'
            "<p>Body</p></c-error-page>"
        )
        assert re.search(r'<span aria-hidden="true"[^>]*>\s*<svg', result)

    def test_status_mark_svg_has_intrinsic_size(self) -> None:
        """The mark must stay small when the stylesheet fails to load.

        Its size-8 class is the only thing holding it back otherwise, so a
        missing stylesheet lets it grow to fill the viewport and buries the
        heading and actions below the fold.
        """
        result = _render(
            '<c-error-page status="500" level="error" '
            'heading="Sorry, there is a problem with this page">'
            "<p>Body</p></c-error-page>"
        )
        mark_svg = re.search(r'<span aria-hidden="true"[^>]*>\s*(<svg[^>]*>)', result)
        assert mark_svg is not None
        assert "width=" in mark_svg.group(1)
        assert "height=" in mark_svg.group(1)

    def test_slot_content_is_rendered(self) -> None:
        result = _render(
            '<c-error-page status="404" heading="We cannot find that page">'
            '<p class="test-marker-body">Check the address for mistakes.</p>'
            "</c-error-page>"
        )
        assert "Check the address for mistakes." in result

    @pytest.mark.parametrize("level", ["neutral", "warning", "error", "info"])
    def test_renders_for_every_level(self, level: str) -> None:
        result = _render(
            f'<c-error-page status="500" level="{level}" '
            'heading="Sorry, there is a problem with this page">'
            "<p>Body</p></c-error-page>"
        )
        assert "Sorry, there is a problem with this page" in result
