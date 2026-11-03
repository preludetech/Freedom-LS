"""Laying sittings out as spreadsheet columns.

The resource that exports applications lives in an app this one must not
import, so it hands sittings in and gets columns and cell text back.
"""

from __future__ import annotations

from collections.abc import Collection, Hashable, Sequence
from dataclasses import dataclass
from uuid import UUID

from django.db.models import prefetch_related_objects

from .conditions import FORM_TREE_LOOKUPS, load_form_tree, sitting_path
from .enums import OPTION_QUESTION_TYPES, QuestionType
from .models import Form, FormProgress, FormQuestion, QuestionAnswer
from .queries import form_questions


@dataclass(frozen=True)
class AnswerColumn:
    """One column of an export: the answers to one question under one header."""

    question: FormQuestion
    header: str


def answer_columns(
    form_progresses: Collection[FormProgress], reserved_headers: Collection[str] = ()
) -> list[AnswerColumn]:
    """The answer columns for these sittings, one per question of each form sat.

    Forms are ordered by title, then id, so an export mixing courses keeps each
    form's questions together. Each form contributes the questions currently
    on its pages, then any answered question on no page of any form in the
    export. A question has one column however many forms it has sat under:
    the form whose page it is on now, else the first form by order that
    answered it. `reserved_headers` are the headers the caller already uses;
    a question with the same text is qualified so the two never clash.
    Expects each sitting's form and answers, with their questions, to be
    prefetched.
    """
    forms = {
        form_progress.form_id: form_progress.form for form_progress in form_progresses
    }
    sittings_by_form: dict[UUID, list[FormProgress]] = {}
    for form_progress in form_progresses:
        sittings_by_form.setdefault(form_progress.form_id, []).append(form_progress)
    ordered_forms = sorted(forms.values(), key=lambda form: (form.title, form.id))
    # Pages load once per form here, not once per sitting.
    prefetch_related_objects(ordered_forms, *FORM_TREE_LOOKUPS)
    on_page_by_form = {form.id: form_questions(form) for form in ordered_forms}
    claimed = {
        question.id for on_page in on_page_by_form.values() for question in on_page
    }
    questions: list[tuple[Form, FormQuestion]] = []
    for form in ordered_forms:
        questions.extend((form, question) for question in on_page_by_form[form.id])
        # A question can leave every page but never be deleted while answered
        # (the answer's FK protects it), so its answers still get a column.
        off_page = {
            answer.question_id: answer.question
            for form_progress in sittings_by_form[form.id]
            for answer in form_progress.answers.all()
            if answer.question_id not in claimed
        }
        claimed.update(off_page)
        questions.extend(
            (form, question)
            for question in sorted(off_page.values(), key=lambda q: (q.order, q.id))
        )
    headers = _qualified(
        [question.question for _, question in questions],
        [form.title for form, _ in questions],
        [form.id for form, _ in questions],
        reserved_headers,
    )
    positions = [str(n) for n in range(1, len(headers) + 1)]
    headers = _qualified(headers, positions, positions, reserved_headers)
    return [
        AnswerColumn(question, header)
        for (_, question), header in zip(questions, headers, strict=True)
    ]


# The scope a reserved header is counted under: never one a question has.
_RESERVED = object()


def _qualified(
    headers: list[str],
    suffixes: list[str],
    scopes: Sequence[Hashable],
    reserved: Collection[str],
) -> list[str]:
    """`headers`, with the suffix appended to each one that another scope repeats.

    Called twice: first with form titles scoped by form, which tells apart two
    forms asking the same thing, then with column positions scoped by column,
    the last resort for one form asking the same thing twice. A header in
    `reserved` counts as already taken, so a question repeating one is
    suffixed too.
    """
    scopes_by_header: dict[str, set[Hashable]] = {
        header: {_RESERVED} for header in reserved
    }
    for header, scope in zip(headers, scopes, strict=True):
        scopes_by_header.setdefault(header, set()).add(scope)
    return [
        f"{header} ({suffix})" if len(scopes_by_header[header]) > 1 else header
        for header, suffix in zip(headers, suffixes, strict=True)
    ]


def off_path_question_ids(
    form_progresses: Collection[FormProgress],
) -> dict[UUID, frozenset[UUID]]:
    """Each sitting's own-form questions its path never reached.

    Loads every form's tree once. A question of another form is in no sitting's
    set. Expects each sitting's answers, with their selected options, to be
    prefetched.
    """
    forms = {
        form_progress.form_id: form_progress.form for form_progress in form_progresses
    }
    for form in forms.values():
        load_form_tree(form)
    on_page_by_form = {
        form_id: frozenset(question.id for question in form_questions(form))
        for form_id, form in forms.items()
    }
    return {
        form_progress.pk: on_page_by_form[form_progress.form_id]
        - sitting_path(
            form_progress,
            {answer.question_id: answer for answer in form_progress.answers.all()},
        ).question_ids
        for form_progress in form_progresses
    }


def answer_value(answer: QuestionAnswer) -> str | list[str] | None:
    """An answer's value by question type; None when the row holds nothing.

    Checkboxes give a list, because several options can be selected; a single
    choice gives one string. Dates and times stay as their stored ISO text: a
    sheet parses that where it would not parse the locale-formatted display text.
    """
    question_type = answer.question.type
    if question_type in OPTION_QUESTION_TYPES:
        options = sorted(answer.selected_options.all(), key=lambda option: option.order)
        texts = [option.text for option in options]
        if not texts:
            return None
        if question_type == QuestionType.CHECKBOXES:
            return texts
        # Multiple choice and dropdown hold one option by design, but a row
        # that somehow holds several must not lose any.
        return "; ".join(texts)
    if question_type == QuestionType.FILE_UPLOAD:
        # The name the applicant gave the file, never its storage key or a URL.
        # hasattr, because a missing reverse one-to-one raises rather than returning None.
        if not hasattr(answer, "answer_file"):
            return None
        return answer.answer_file.original_filename or None
    return answer.text_answer or None


def answer_cell(answer: QuestionAnswer | None, *, is_asked: bool = True) -> str:
    """One answer as spreadsheet text.

    "Not asked" for a question the sitting's path never reached; an empty cell
    for one it reached and the applicant left unanswered.
    """
    if not is_asked:
        return "Not asked"
    if answer is None:
        return ""
    value = answer_value(answer)
    if value is None:
        return ""
    if isinstance(value, list):
        return "; ".join(value)
    return value
