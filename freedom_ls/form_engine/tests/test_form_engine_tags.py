"""The `answer_display` filter: a stored answer rendered for a reader."""

from __future__ import annotations

import pytest

from django.template import Context, Template

from freedom_ls.form_engine.enums import QuestionType
from freedom_ls.form_engine.templatetags.form_engine_tags import answer_display


@pytest.mark.parametrize(
    ("question_type", "text_answer", "expected"),
    [
        (QuestionType.DATE, "1987-03-14", "March 14, 1987"),
        (QuestionType.TIME, "14:30", "2:30 p.m."),
        (QuestionType.SHORT_TEXT, "Freda", "Freda"),
    ],
)
def test_answer_display_delegates_to_format_answer(
    question_type: str, text_answer: str, expected: str
) -> None:
    assert answer_display(text_answer, question_type) == expected


def test_answer_display_falls_back_to_the_raw_string_when_it_will_not_parse() -> None:
    """A row written before `date` existed, or under a question whose `type`
    changed afterwards, still has to render as something.
    """
    assert answer_display("banana", QuestionType.DATE) == "banana"


def test_a_non_string_text_answer_renders_harmlessly_rather_than_raising() -> None:
    """A template variable never added to the context resolves to the empty
    string, not `None` -- the filter must not raise mid-render.
    """
    assert answer_display(None, QuestionType.DATE) == ""


def test_a_non_string_question_type_renders_the_raw_answer() -> None:
    assert answer_display("Freda", None) == "Freda"


def test_answer_display_renders_through_a_template() -> None:
    rendered = Template(
        "{% load form_engine_tags %}{{ text_answer|answer_display:question_type }}"
    ).render(Context({"text_answer": "1987-03-14", "question_type": QuestionType.DATE}))

    assert rendered == "March 14, 1987"
