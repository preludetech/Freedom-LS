"""The pydantic schema is what an author's content files are validated against,
so it has to accept the same strategy and question-type vocabulary the models
do. These are the members application forms add.
"""

from __future__ import annotations

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
