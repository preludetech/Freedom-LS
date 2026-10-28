"""Tests for laying sittings out as spreadsheet columns."""

from __future__ import annotations

import pytest

from freedom_ls.form_engine.exports import answer_cell, answer_columns
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionAnswerFileFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import FormProgress, QuestionAnswer
from freedom_ls.form_engine.queries import form_questions

pytestmark = pytest.mark.django_db


def _answer(question_type: str, **answer_fields: str) -> QuestionAnswer:
    question = FormQuestionFactory(type=question_type)
    answer: QuestionAnswer = QuestionAnswerFactory(question=question, **answer_fields)
    return answer


def test_answer_columns_follow_form_questions_order_with_the_question_text_as_header(
    mock_site_context,
):
    form = FormFactory()
    first_page = FormPageFactory(form=form, order=0)
    second_page = FormPageFactory(form=form, order=1)
    FormQuestionFactory(form_page=second_page, order=0, question="Third")
    FormQuestionFactory(form_page=first_page, order=1, question="Second")
    FormQuestionFactory(form_page=first_page, order=0, question="First")
    sitting: FormProgress = FormProgressFactory(form=form)

    columns = answer_columns([sitting])

    assert [column.header for column in columns] == ["First", "Second", "Third"]
    assert [column.question for column in columns] == form_questions(form)


def test_answer_cell_of_no_answer_is_empty(mock_site_context):
    assert answer_cell(None) == ""


def test_answer_cell_of_a_multiple_choice_answer_is_the_option_text(
    mock_site_context,
):
    answer = _answer("multiple_choice")
    option = QuestionOptionFactory(question=answer.question, text="Search")
    answer.selected_options.add(option)

    assert answer_cell(answer) == "Search"


def test_answer_cell_of_a_checkboxes_answer_joins_option_texts_in_option_order(
    mock_site_context,
):
    answer = _answer("checkboxes")
    third = QuestionOptionFactory(question=answer.question, text="C", order=2)
    first = QuestionOptionFactory(question=answer.question, text="A", order=0)
    second = QuestionOptionFactory(question=answer.question, text="B", order=1)
    answer.selected_options.add(third, first, second)

    assert answer_cell(answer) == "A; B; C"


def test_answer_cell_of_a_dropdown_answer_is_the_option_text(mock_site_context):
    answer = _answer("dropdown")
    option = QuestionOptionFactory(question=answer.question, text="Cape Town")
    answer.selected_options.add(option)

    assert answer_cell(answer) == "Cape Town"


def test_answer_cell_of_a_file_upload_is_the_original_filename(mock_site_context):
    answer = _answer("file_upload")
    QuestionAnswerFileFactory(answer=answer, original_filename="id-scan.png")

    assert answer_cell(answer) == "id-scan.png"


def test_answer_cell_of_a_file_upload_without_a_file_is_empty(mock_site_context):
    answer = _answer("file_upload")

    assert answer_cell(answer) == ""


@pytest.mark.parametrize(
    ("question_type", "stored"), [("date", "1990-02-03"), ("time", "09:30")]
)
def test_answer_cell_of_a_date_or_time_is_the_stored_text(
    mock_site_context, question_type, stored
):
    answer = _answer(question_type, text_answer=stored)

    assert answer_cell(answer) == stored


def test_answer_cell_of_a_long_text_answer_keeps_its_newlines(mock_site_context):
    answer = _answer("long_text", text_answer="line one\nline two\n")

    assert answer_cell(answer) == "line one\nline two\n"
