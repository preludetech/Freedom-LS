"""form_engine/answers/: a submitted answer drawn for a reader, with no form fields."""

from __future__ import annotations

from typing import cast

import lxml.html
import pytest

from django.template.loader import render_to_string

from freedom_ls.form_engine.factories import (
    FormPageFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionAnswerFileFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import FormQuestion, QuestionAnswer

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("mock_site_context")]

FORM_CONTROLS = "input, select, textarea, button"


def _question(question_type: str) -> FormQuestion:
    return cast(
        FormQuestion,
        FormQuestionFactory(
            form_page=FormPageFactory(), type=question_type, question="Which one?"
        ),
    )


def _choice(question_type: str) -> tuple[FormQuestion, QuestionAnswer]:
    """A question with options Alpha (correct), Beta and Gamma; the learner chose Beta."""
    question = _question(question_type)
    QuestionOptionFactory(question=question, text="Alpha", correct=True, order=1)
    chosen = QuestionOptionFactory(question=question, text="Beta", order=2)
    QuestionOptionFactory(question=question, text="Gamma", order=3)
    answer = cast(QuestionAnswer, QuestionAnswerFactory(question=question))
    answer.selected_options.add(chosen)
    return question, answer


def _render(
    question: FormQuestion, answer: QuestionAnswer | None, **extra: object
) -> lxml.html.HtmlElement:
    html = render_to_string(
        "form_engine/answers/question.html",
        {
            "question": question,
            "question_positions": {question.id: 3},
            "existing_answers": {question.id: answer} if answer else {},
            **extra,
        },
    )
    return lxml.html.fragment_fromstring(html, create_parent="div")


def _rows(document: lxml.html.HtmlElement) -> list[str]:
    return [
        " ".join(row.text_content().split())
        for row in document.cssselect("[data-testid='answer-option']")
    ]


def test_the_question_shows_its_number_id_and_text() -> None:
    question = _question("long_text")

    text = _render(question, None).text_content()

    assert "3." in text
    assert str(question.id) in text
    assert "Which one?" in text


def test_the_question_id_sits_under_the_question_text_as_code() -> None:
    question = _question("long_text")

    document = _render(question, None)

    (question_text,) = document.cssselect("[data-testid='question-text']")
    (question_id,) = document.cssselect("[data-testid='question-id']")
    assert question_id.tag == "code"
    assert question_id.text_content() == str(question.id)
    assert question_text.getnext() is question_id


@pytest.mark.parametrize("question_type", ["long_text", "short_text", "number", "date"])
def test_a_text_answer_reads_as_text_under_the_learner_answer_label(
    question_type: str,
) -> None:
    question = _question(question_type)
    answer = cast(
        QuestionAnswer,
        QuestionAnswerFactory(question=question, text_answer="Point out the exits"),
    )

    document = _render(question, answer)

    assert document.cssselect(FORM_CONTROLS) == []
    (block,) = document.cssselect("[data-testid='text-answer']")
    assert "Learner's answer" in block.text_content()
    assert "Point out the exits" in block.text_content()


@pytest.mark.parametrize("question_type", ["long_text", "file_upload"])
def test_an_answer_box_is_outlined_like_a_chosen_option_not_an_admonition(
    question_type: str,
) -> None:
    question = _question(question_type)
    answer = cast(
        QuestionAnswer, QuestionAnswerFactory(question=question, text_answer="Yes")
    )
    if question_type == "file_upload":
        QuestionAnswerFileFactory(answer=answer, original_filename="licence.pdf")

    document = _render(question, answer)

    (block,) = document.cssselect("[data-testid='text-answer']")
    classes = block.get("class").split()
    assert {"border", "border-primary", "bg-primary/5", "rounded-md"} <= set(classes)
    assert "border-s-4" not in classes


def test_a_file_answer_shows_its_name_and_size() -> None:
    question = _question("file_upload")
    answer = cast(QuestionAnswer, QuestionAnswerFactory(question=question))
    QuestionAnswerFileFactory(answer=answer, original_filename="licence.pdf")

    text = " ".join(_render(question, answer).text_content().split())

    assert "licence.pdf (12 bytes)" in text


def test_a_file_answer_missing_from_storage_shows_its_name_without_a_size() -> None:
    question = _question("file_upload")
    answer = cast(QuestionAnswer, QuestionAnswerFactory(question=question))
    stored = QuestionAnswerFileFactory(answer=answer, original_filename="licence.pdf")
    stored.file.storage.delete(stored.file.name)

    text = " ".join(_render(question, answer).text_content().split())

    assert "licence.pdf" in text
    assert "bytes" not in text


def test_a_long_text_answer_keeps_its_line_breaks() -> None:
    question = _question("long_text")
    answer = cast(
        QuestionAnswer,
        QuestionAnswerFactory(question=question, text_answer="One\nTwo"),
    )

    document = _render(question, answer)

    (text,) = document.cssselect("[data-testid='text-answer'] p")
    assert "whitespace-pre-line" in text.get("class")
    assert text.text_content() == "One\nTwo"


def test_an_unanswered_text_question_shows_no_answer_block() -> None:
    question = _question("long_text")

    document = _render(question, None)

    assert document.cssselect("[data-testid='text-answer']") == []
    assert "Learner's answer" not in document.text_content()


@pytest.mark.parametrize(
    ("question_type", "indicator"),
    [
        ("multiple_choice", "radio"),
        ("dropdown", "radio"),
        ("checkboxes", "checkbox"),
    ],
)
def test_a_choice_question_lists_every_option_and_marks_the_chosen_one(
    question_type: str, indicator: str
) -> None:
    question, answer = _choice(question_type)

    document = _render(question, answer, show_answer_key=True)

    assert document.cssselect(FORM_CONTROLS) == []
    assert _rows(document) == [
        "Alpha Correct answer",
        "Beta Learner's answer",
        "Gamma",
    ]
    assert len(document.cssselect(f"[data-testid='{indicator}-indicator']")) == 3


def test_every_chosen_checkbox_option_carries_the_learner_mark() -> None:
    question, answer = _choice("checkboxes")
    answer.selected_options.add(question.options.get(text="Alpha"))

    document = _render(question, answer, show_answer_key=True)

    assert _rows(document) == [
        "Alpha Learner's answer Correct answer",
        "Beta Learner's answer",
        "Gamma",
    ]


def test_the_correct_mark_needs_the_answer_key() -> None:
    question, answer = _choice("multiple_choice")

    document = _render(question, answer)

    assert "Correct answer" not in document.text_content()


def test_a_file_answer_names_the_file_and_offers_no_upload() -> None:
    question = _question("file_upload")
    answer = cast(QuestionAnswer, QuestionAnswerFactory(question=question))
    QuestionAnswerFileFactory(answer=answer, original_filename="licence.pdf")

    document = _render(question, answer)

    assert document.cssselect(FORM_CONTROLS) == []
    (block,) = document.cssselect("[data-testid='text-answer']")
    assert "Learner's answer" in block.text_content()
    assert "licence.pdf" in block.text_content()
