"""Tests for the <c-course-card-shell /> and <c-course-row-shell /> eyebrow slot."""

import pytest
from django_cotton.compiler_regex import CottonCompiler

from django.template import Context, Template

_cotton_compiler = CottonCompiler()

ROW_EYEBROW_WRAPPER = "justify-between"
CARD_BODY_START = '<div class="pt-3 flex-1 flex flex-col space-y-2">'


def _render(component: str, eyebrow: str) -> str:
    processed = _cotton_compiler.process(
        f'<c-{component} accent_slot_key="1" icon="" icon_fallback="" title="T">'
        f'<c-slot name="eyebrow">{eyebrow}</c-slot>'
        "<h3>T</h3>"
        f"</c-{component}>"
    )
    return Template(processed).render(Context({}))


@pytest.mark.django_db
def test_row_shell_skips_the_eyebrow_line_when_both_halves_are_empty(
    mock_site_context,
):
    result = _render("course-row-shell", "<div></div>\n<div class='ml-auto'>\n</div>")

    assert ROW_EYEBROW_WRAPPER not in result


@pytest.mark.django_db
def test_row_shell_draws_the_eyebrow_line_around_a_chip(mock_site_context):
    result = _render("course-row-shell", "<div><span>Beginner</span></div><div></div>")

    assert ROW_EYEBROW_WRAPPER in result
    assert "Beginner" in result


@pytest.mark.django_db
def test_card_shell_skips_the_eyebrow_wrapper_for_a_whitespace_slot(
    mock_site_context,
):
    result = _render("course-card-shell", "\n    \n")

    body = result.split(CARD_BODY_START, 1)[1]
    assert body.lstrip().startswith("<h3>")


@pytest.mark.django_db
def test_card_shell_wraps_an_eyebrow_with_text(mock_site_context):
    result = _render("course-card-shell", "<p>Registered</p>")

    body = result.split(CARD_BODY_START, 1)[1]
    assert body.lstrip().startswith("<div><p>Registered</p></div>")
