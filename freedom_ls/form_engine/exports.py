"""Laying sittings out as spreadsheet columns.

The resource that exports applications lives in an app this one must not
import, so it hands sittings in and gets columns and cell text back.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from django.db.models import prefetch_related_objects

from .enums import OPTION_QUESTION_TYPES, QuestionType
from .models import FormProgress, FormQuestion, QuestionAnswer
from .queries import form_questions


@dataclass(frozen=True)
class AnswerColumn:
    """One column of an export: the answers to one question under one header."""

    question: FormQuestion
    header: str


def answer_columns(form_progresses: Collection[FormProgress]) -> list[AnswerColumn]:
    """The answer columns for these sittings, one per question of each form sat.

    Forms are ordered by title, then id, so an export mixing courses keeps each
    form's questions together. Expects each sitting's form and answers, with
    their questions, to be prefetched.
    """
    forms = {
        form_progress.form_id: form_progress.form for form_progress in form_progresses
    }
    ordered_forms = sorted(forms.values(), key=lambda form: (form.title, form.id))
    # Pages load once per form here, not once per sitting.
    prefetch_related_objects(ordered_forms, "pages__text_items", "pages__questions")
    return [
        AnswerColumn(question, question.question)
        for form in ordered_forms
        for question in form_questions(form)
    ]


def answer_cell(answer: QuestionAnswer | None) -> str:
    """One answer as spreadsheet text; an empty cell for a question never answered."""
    if answer is None:
        return ""
    question_type = answer.question.type
    if question_type in OPTION_QUESTION_TYPES:
        options = sorted(answer.selected_options.all(), key=lambda option: option.order)
        return "; ".join(option.text for option in options)
    if question_type == QuestionType.FILE_UPLOAD:
        # The name the applicant gave the file, never its storage key or a URL.
        # hasattr, because a missing reverse one-to-one raises rather than returning None.
        if not hasattr(answer, "answer_file"):
            return ""
        return answer.answer_file.original_filename
    # Dates and times stay as their stored ISO text: a sheet parses that where
    # it would not parse the locale-formatted display text.
    return answer.text_answer
