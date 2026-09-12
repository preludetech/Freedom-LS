"""The pydantic schema is what an author's content files are validated against,
so it has to accept the same strategy and question-type vocabulary the models
do. These are the members application forms add.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from freedom_ls.form_engine.schema import Form, FormQuestion, FormStrategy, QuestionType


def test_unscored_form_validates_without_the_quiz_fields():
    form = Form.model_validate(
        {
            "content_type": "FORM",
            "file_path": "forms/application/form.md",
            "title": "Application form",
            "strategy": "UNSCORED",
        }
    )

    assert form.strategy == FormStrategy.UNSCORED


def test_file_upload_question_validates():
    question = FormQuestion.model_validate(
        {
            "content_type": "FORM_QUESTION",
            "file_path": "forms/application/1. documents.yaml",
            "question": "Upload a scan of your ID",
            "type": "file_upload",
        }
    )

    assert question.type == QuestionType.FILE_UPLOAD


def test_number_question_validates():
    question = FormQuestion.model_validate(
        {
            "content_type": "FORM_QUESTION",
            "file_path": "forms/application/1. about-you.yaml",
            "question": "How many years of experience do you have?",
            "type": "number",
        }
    )

    assert question.type == QuestionType.NUMBER


def test_date_question_validates():
    question = FormQuestion.model_validate(
        {
            "content_type": "FORM_QUESTION",
            "file_path": "forms/application/1. about-you.yaml",
            "question": "What is your date of birth?",
            "type": "date",
        }
    )

    assert question.type == QuestionType.DATE


def test_time_question_validates():
    question = FormQuestion.model_validate(
        {
            "content_type": "FORM_QUESTION",
            "file_path": "forms/application/3. availability.yaml",
            "question": "What time can you start?",
            "type": "time",
        }
    )

    assert question.type == QuestionType.TIME


def test_email_question_validates():
    question = FormQuestion.model_validate(
        {
            "content_type": "FORM_QUESTION",
            "file_path": "forms/application/1. about-you.yaml",
            "question": "What is your email address?",
            "type": "email",
        }
    )

    assert question.type == QuestionType.EMAIL


def test_url_question_validates():
    question = FormQuestion.model_validate(
        {
            "content_type": "FORM_QUESTION",
            "file_path": "forms/application/1. about-you.yaml",
            "question": "Link to your portfolio?",
            "type": "url",
        }
    )

    assert question.type == QuestionType.URL


def test_phone_question_validates():
    question = FormQuestion.model_validate(
        {
            "content_type": "FORM_QUESTION",
            "file_path": "forms/application/1. about-you.yaml",
            "question": "What is your phone number?",
            "type": "phone",
        }
    )

    assert question.type == QuestionType.PHONE


def test_dropdown_question_validates():
    question = FormQuestion.model_validate(
        {
            "content_type": "FORM_QUESTION",
            "file_path": "forms/application/3. availability.yaml",
            "question": "Which region are you based in?",
            "type": "dropdown",
            "options": [
                {"text": "North", "value": 1},
                {"text": "South", "value": 2},
            ],
        }
    )

    assert question.type == QuestionType.DROPDOWN


# min / max


def test_date_question_with_valid_min_and_max_validates():
    question = FormQuestion.model_validate(
        {
            "content_type": "FORM_QUESTION",
            "file_path": "forms/application/1. about-you.yaml",
            "question": "What is your date of birth?",
            "type": "date",
            "min": "1930-01-01",
            "max": "2010-12-31",
        }
    )

    assert question.min == "1930-01-01"
    assert question.max == "2010-12-31"


def test_min_of_zero_coerces_to_a_string():
    """An unquoted `min: 0` in YAML resolves to a Python int, not a str."""
    question = FormQuestion.model_validate(
        {
            "content_type": "FORM_QUESTION",
            "file_path": "forms/application/1. about-you.yaml",
            "question": "How many years of experience do you have?",
            "type": "number",
            "min": 0,
        }
    )

    assert question.min == "0"


def test_unquoted_date_bound_coerces_to_a_string():
    """An unquoted date in YAML resolves to a `datetime.date`, not a str."""
    question = FormQuestion.model_validate(
        {
            "content_type": "FORM_QUESTION",
            "file_path": "forms/application/1. about-you.yaml",
            "question": "What is your date of birth?",
            "type": "date",
            "min": date(1930, 1, 1),
        }
    )

    assert question.min == "1930-01-01"


def test_min_on_an_email_question_is_refused():
    with pytest.raises(ValidationError):
        FormQuestion.model_validate(
            {
                "content_type": "FORM_QUESTION",
                "file_path": "forms/application/1. about-you.yaml",
                "question": "What is your email address?",
                "type": "email",
                "min": "1",
            }
        )


def test_min_that_does_not_parse_as_a_date_is_refused():
    with pytest.raises(ValidationError):
        FormQuestion.model_validate(
            {
                "content_type": "FORM_QUESTION",
                "file_path": "forms/application/1. about-you.yaml",
                "question": "What is your date of birth?",
                "type": "date",
                "min": "banana",
            }
        )


def test_unquoted_time_bound_turned_integer_by_yaml_is_refused():
    """YAML 1.1 reads an unquoted `09:05` as the base-60 integer 545, which
    coerces to the string "545" — not a valid time."""
    with pytest.raises(ValidationError):
        FormQuestion.model_validate(
            {
                "content_type": "FORM_QUESTION",
                "file_path": "forms/application/3. availability.yaml",
                "question": "What time can you start?",
                "type": "time",
                "max": 545,
            }
        )


def test_unquoted_time_bound_that_still_parses_is_refused():
    """The dangerous half of the same mistake. An unquoted `17:00` becomes the
    integer 1020, and `parse_time` accepts "1020" as ten past ten — so a parse
    check alone lets it through as a different time than the author wrote. It
    has to be refused on its shape."""
    with pytest.raises(ValidationError):
        FormQuestion.model_validate(
            {
                "content_type": "FORM_QUESTION",
                "file_path": "forms/application/3. availability.yaml",
                "question": "What time can you finish?",
                "type": "time",
                "max": 1020,
            }
        )
