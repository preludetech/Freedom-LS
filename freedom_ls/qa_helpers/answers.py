"""Helpers for the QA fixture commands that write answer rows directly."""

from __future__ import annotations

from collections.abc import Sequence

from freedom_ls.form_engine.models import QuestionAnswer, latest_versions


def pin_to_latest_versions(answers: Sequence[QuestionAnswer]) -> None:
    """Record each answer's question's latest version on it.

    The fixture commands write answer rows without going through
    `FormProgress.save_answers()`, which is what normally records the version.
    A question with no version leaves its answer's version as None.
    """
    latest = latest_versions({answer.question_id for answer in answers})
    for answer in answers:
        answer.question_version = latest.get(answer.question_id)
    QuestionAnswer.objects.bulk_update(list(answers), ["question_version"])
