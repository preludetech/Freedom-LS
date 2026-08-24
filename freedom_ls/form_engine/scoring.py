from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from .models import QuestionOption


def is_quiz_answer_correct(
    selected_option_ids: set[UUID], options: Iterable[QuestionOption]
) -> bool:
    """Exact-match scoring: every correct option selected, no incorrect one.

    `QuestionOption.correct` is nullable. `True` is required, `False` is forbidden,
    `None` is neither - an option nobody marked up is not evidence either way.
    A question with no correct option cannot be answered correctly; that keeps
    free-text questions (which have no options at all) scoring zero, as they do today.
    """
    required = {o.id for o in options if o.correct is True}
    forbidden = {o.id for o in options if o.correct is False}
    if not required:
        return False
    return required <= selected_option_ids and not (selected_option_ids & forbidden)


def evaluate_quiz_answers(
    answer_rows: Iterable[tuple[UUID, UUID, set[UUID]]],
    options_by_question: Mapping[UUID, list[QuestionOption]],
) -> dict[tuple[UUID, UUID], bool]:
    """Correctness for many (attempt, question) pairs from pre-fetched data. Issues no queries."""
    return {
        (form_progress_id, question_id): is_quiz_answer_correct(
            selected_option_ids, options_by_question.get(question_id, [])
        )
        for form_progress_id, question_id, selected_option_ids in answer_rows
    }
