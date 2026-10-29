"""Tests for the <c-callout /> cotton component's text colours."""

import pytest
from django_cotton.compiler_regex import CottonCompiler

from django.template import Context, Template

_cotton_compiler = CottonCompiler()


def _render(template_string: str) -> str:
    return Template(_cotton_compiler.process(template_string)).render(Context())


@pytest.mark.parametrize("level", ["warning", "success"])
def test_callout_text_is_not_the_background_only_status_colour(level: str) -> None:
    """Sand and Forest used as text on their own pale tint were barely readable."""
    result = _render(f'<c-callout level="{level}" title="Heads up">Body</c-callout>')

    assert f'class="text-{level}' not in result
    assert f"text-xl font-semibold text-{level} " not in result
    assert f"text-on-{level}-light" in result


def test_callout_puts_a_passed_class_on_its_box() -> None:
    result = _render(
        '<c-callout level="warning" class="mx-auto max-w-reading">Body</c-callout>'
    )

    assert "rounded-r-lg mx-auto max-w-reading" in result
