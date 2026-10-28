"""Laying sittings out as spreadsheet columns.

The resource that exports applications lives in an app this one must not
import, so it hands sittings in and gets columns and cell text back.
"""

from __future__ import annotations

from collections.abc import Collection, Hashable, Sequence
from dataclasses import dataclass
from uuid import UUID

from django.db.models import prefetch_related_objects

from .enums import OPTION_QUESTION_TYPES, QuestionType
from .models import Form, FormProgress, FormQuestion, QuestionAnswer
from .queries import form_questions


@dataclass(frozen=True)
class AnswerColumn:
    """One column of an export: the answers to one question under one header."""

    question: FormQuestion
    header: str


def answer_columns(form_progresses: Collection[FormProgress]) -> list[AnswerColumn]:
    """The answer columns for these sittings, one per question of each form sat.

    Forms are ordered by title, then id, so an export mixing courses keeps each
    form's questions together. Each form contributes the questions currently
    on its pages, then any question off every page that one of these sittings
    answered. Expects each sitting's form and answers, with their questions,
    to be prefetched.
    """
    forms = {
        form_progress.form_id: form_progress.form for form_progress in form_progresses
    }
    sittings_by_form: dict[UUID, list[FormProgress]] = {}
    for form_progress in form_progresses:
        sittings_by_form.setdefault(form_progress.form_id, []).append(form_progress)
    ordered_forms = sorted(forms.values(), key=lambda form: (form.title, form.id))
    # Pages load once per form here, not once per sitting.
    prefetch_related_objects(ordered_forms, "pages__text_items", "pages__questions")
    questions: list[tuple[Form, FormQuestion]] = []
    for form in ordered_forms:
        on_page = form_questions(form)
        on_page_ids = {question.id for question in on_page}
        questions.extend((form, question) for question in on_page)
        # A question can leave every page but never be deleted while answered
        # (the answer's FK protects it), so its answers still get a column.
        off_page = {
            answer.question_id: answer.question
            for form_progress in sittings_by_form[form.id]
            for answer in form_progress.answers.all()
            if answer.question_id not in on_page_ids
        }
        questions.extend(
            (form, question)
            for question in sorted(off_page.values(), key=lambda q: (q.order, q.id))
        )
    headers = _qualified(
        [question.question for _, question in questions],
        [form.title for form, _ in questions],
        [form.id for form, _ in questions],
    )
    positions = [str(n) for n in range(1, len(headers) + 1)]
    headers = _qualified(headers, positions, positions)
    return [
        AnswerColumn(question, header)
        for (_, question), header in zip(questions, headers, strict=True)
    ]


def _qualified(
    headers: list[str], suffixes: list[str], scopes: Sequence[Hashable]
) -> list[str]:
    """`headers`, with the suffix appended to each one that another scope repeats.

    Called twice: first with form titles scoped by form, which tells apart two
    forms asking the same thing, then with column positions scoped by column,
    the last resort for one form asking the same thing twice.
    """
    scopes_by_header: dict[str, set[Hashable]] = {}
    for header, scope in zip(headers, scopes, strict=True):
        scopes_by_header.setdefault(header, set()).add(scope)
    return [
        f"{header} ({suffix})" if len(scopes_by_header[header]) > 1 else header
        for header, suffix in zip(headers, suffixes, strict=True)
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
