"""Tests for laying sittings out as spreadsheet columns."""

from __future__ import annotations

from uuid import uuid4

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


def _sitting_of(title: str, *question_texts: str) -> FormProgress:
    form = FormFactory(title=title, slug=f"{title}-{uuid4()}")
    page = FormPageFactory(form=form)
    for order, text in enumerate(question_texts):
        FormQuestionFactory(form_page=page, order=order, question=text)
    sitting: FormProgress = FormProgressFactory(form=form)
    return sitting


def test_answer_columns_of_several_forms_are_ordered_by_form_title(
    mock_site_context,
):
    b_sitting = _sitting_of("B form", "B question")
    a_sitting = _sitting_of("A form", "A question")

    columns = answer_columns([b_sitting, a_sitting])

    assert [column.header for column in columns] == ["A question", "B question"]


def test_an_answered_question_off_every_page_gets_a_column_after_the_page_questions(
    mock_site_context,
):
    form = FormFactory()
    FormQuestionFactory(form_page=FormPageFactory(form=form), question="On page")
    moved = FormQuestionFactory(
        form_page=FormPageFactory(form=FormFactory()), question="Moved"
    )
    sitting: FormProgress = FormProgressFactory(form=form)
    QuestionAnswerFactory(form_progress=sitting, question=moved)

    columns = answer_columns([sitting])

    assert [column.header for column in columns] == ["On page", "Moved"]
    assert columns[-1].question == moved


def test_a_question_moved_to_another_exported_form_gets_one_column_under_that_form(
    mock_site_context,
):
    old_sitting = _sitting_of("A form", "Stays")
    new_sitting = _sitting_of("B form", "Moved")
    moved = new_sitting.form.pages.get().questions.get()
    QuestionAnswerFactory(form_progress=old_sitting, question=moved)

    columns = answer_columns([old_sitting, new_sitting])

    assert [column.header for column in columns] == ["Stays", "Moved"]
    assert columns[-1].question == moved


def test_a_question_off_every_page_answered_under_two_forms_gets_one_column(
    mock_site_context,
):
    sittings = [_sitting_of("A form", "A question"), _sitting_of("B form")]
    gone = FormQuestionFactory(
        form_page=FormPageFactory(form=FormFactory()), question="Gone"
    )
    for sitting in sittings:
        QuestionAnswerFactory(form_progress=sitting, question=gone)

    columns = answer_columns(sittings)

    assert [column.header for column in columns] == ["A question", "Gone"]


def test_a_question_titled_like_a_reserved_header_gets_its_form_title_appended(
    mock_site_context,
):
    sitting = _sitting_of("Only form", "course", "Why?")

    columns = answer_columns([sitting], reserved_headers=["course", "id"])

    assert [column.header for column in columns] == ["course (Only form)", "Why?"]


def test_forms_asking_the_same_question_get_their_form_title_in_the_header(
    mock_site_context,
):
    sittings = [_sitting_of("B form", "Why?"), _sitting_of("A form", "Why?")]

    columns = answer_columns(sittings)

    assert [column.header for column in columns] == ["Why? (A form)", "Why? (B form)"]


def test_one_form_asking_the_same_question_twice_gets_column_positions_in_the_header(
    mock_site_context,
):
    sitting = _sitting_of("Only form", "Why?", "Why?")

    columns = answer_columns([sitting])

    assert [column.header for column in columns] == ["Why? (1)", "Why? (2)"]


def test_forms_with_the_same_title_asking_the_same_question_get_both_suffixes(
    mock_site_context,
):
    sittings = [_sitting_of("Same", "Why?"), _sitting_of("Same", "Why?")]

    columns = answer_columns(sittings)

    assert [column.header for column in columns] == [
        "Why? (Same) (1)",
        "Why? (Same) (2)",
    ]


def test_a_question_text_used_by_one_form_only_keeps_its_bare_header(
    mock_site_context,
):
    sittings = [_sitting_of("A form", "Unique", "Twice", "Twice")]
    sittings.append(_sitting_of("B form", "Other"))

    columns = answer_columns(sittings)

    assert [column.header for column in columns] == [
        "Unique",
        "Twice (2)",
        "Twice (3)",
        "Other",
    ]
