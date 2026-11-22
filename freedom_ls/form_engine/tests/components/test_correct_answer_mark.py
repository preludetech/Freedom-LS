"""Tests for the <c-correct-answer-mark /> cotton component."""

from django_cotton.compiler_regex import CottonCompiler

from django.template import Context, Template

_cotton_compiler = CottonCompiler()


def _render(attrs: str = "") -> str:
    processed = _cotton_compiler.process(f"<c-correct-answer-mark {attrs} />")
    return Template(processed).render(Context({}))


def test_wrong_choice_renders_your_answer_in_the_error_colour():
    html = _render('wrong_choice="true"')

    assert "Your answer" in html
    assert "text-error" in html
    assert "Correct answer" not in html


def test_without_wrong_choice_it_marks_the_correct_answer():
    html = _render()

    assert "Correct answer" in html
    assert "text-success" in html
    assert "Your answer" not in html


def test_option_text_is_appended_to_the_correct_answer_mark():
    html = _render('option_text="Paris"')

    assert "Correct answer: Paris" in html
