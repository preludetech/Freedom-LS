from __future__ import annotations

from typing import TYPE_CHECKING

from freedom_ls.content_engine.models import FREE_TEXT_QUESTION_TYPES

if TYPE_CHECKING:
    from django.http import QueryDict

    from freedom_ls.content_engine.models import FormQuestion


def submitted_option_ids(question: FormQuestion, post_data: QueryDict) -> list[str]:
    """Option IDs submitted for a choice question, ignoring blank values."""
    return [value for value in post_data.getlist(f"question_{question.id}") if value]


def submitted_text_answer(question: FormQuestion, post_data: QueryDict) -> str:
    """Trimmed text submitted for a free-text question."""
    return post_data.get(f"question_{question.id}", "").strip()


def has_submitted_answer(question: FormQuestion, post_data: QueryDict) -> bool:
    """Whether `post_data` carries an answer to `question`.

    Choice questions need at least one selected option, free-text questions need
    non-blank text. This is what `FormQuestion.required` is measured against, and
    what decides whether an answer row is stored at all.
    """
    if question.type in FREE_TEXT_QUESTION_TYPES:
        return bool(submitted_text_answer(question, post_data))
    return bool(submitted_option_ids(question, post_data))
