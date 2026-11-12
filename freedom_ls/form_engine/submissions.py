from __future__ import annotations

from typing import TYPE_CHECKING

from .enums import FREE_TEXT_QUESTION_TYPES, QuestionType
from .phone_numbers import SUPPORTED_REGIONS

if TYPE_CHECKING:
    from django.http import QueryDict

    from .models import FormQuestion


def submitted_option_ids(question: FormQuestion, post_data: QueryDict) -> list[str]:
    """Option IDs submitted for a choice question, ignoring blank values."""
    return [value for value in post_data.getlist(f"question_{question.id}") if value]


def submitted_text_answer(question: FormQuestion, post_data: QueryDict) -> str:
    """Trimmed text submitted for a free-text question."""
    return post_data.get(f"question_{question.id}", "").strip()


def submitted_phone_country(question: FormQuestion, post_data: QueryDict) -> str:
    """The country selected beside a phone question, or "" for none.

    The key sits outside the `question_` prefix: the exam runner counts every
    `question_*` field as a question, and a preselected country is not an answer.
    Anything that is not a country on offer reads as none, so a hand-built POST
    cannot put an arbitrary string into a message or a lookup.
    """
    country = post_data.get(f"phone_country_{question.id}", "")
    return country if country in SUPPORTED_REGIONS else ""


def has_submitted_answer(question: FormQuestion, post_data: QueryDict) -> bool:
    """Whether `post_data` carries an answer to `question`.

    Choice questions need at least one selected option, free-text questions need
    non-blank text. This is what `FormQuestion.required` is measured against, and
    what decides whether an answer row is stored at all.

    A file question is always False: its answer arrives on its own request and
    lives in a stored row, so the page POST never carries one.
    """
    if question.type == QuestionType.FILE_UPLOAD:
        return False
    if question.type in FREE_TEXT_QUESTION_TYPES:
        return bool(submitted_text_answer(question, post_data))
    return bool(submitted_option_ids(question, post_data))
