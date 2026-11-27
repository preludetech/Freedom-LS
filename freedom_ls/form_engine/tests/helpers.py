"""Helpers shared by form_engine tests."""

from __future__ import annotations

from collections.abc import Sequence

from freedom_ls.form_engine.models import (
    FormQuestion,
    FormQuestionVersion,
    QuestionOption,
    save_question_version,
)


def revise_question(
    question: FormQuestion,
    /,
    *,
    options: Sequence[dict[str, object]] | None = None,
    **fields: object,
) -> FormQuestionVersion:
    """Edit the live question, and its options when `options` is given, then save the
    next version. Each option dict holds the fields to set on the option, plus `id`
    to change an existing one; one without an `id` is created. `question` is
    positional-only because it is also the name of a question field."""
    for name, value in fields.items():
        setattr(question, name, value)
    question.save()
    for spec in options or []:
        fields_to_set = {k: v for k, v in spec.items() if k != "id"}
        if "id" in spec:
            QuestionOption.objects.filter(pk=spec["id"]).update(**fields_to_set)
        else:
            QuestionOption.objects.create(
                question=question, site_id=question.site_id, **fields_to_set
            )
    version = save_question_version(question, list(question.options.all()), "revision")
    assert version.version is not None
    return version.version
