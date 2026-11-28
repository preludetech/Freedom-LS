"""Helpers shared by form_engine tests."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from freedom_ls.form_engine.conditions import ServedPaper
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import (
    Form,
    FormQuestion,
    FormQuestionVersion,
    FormStrategy,
    QuestionOption,
    save_question_version,
)
from freedom_ls.form_engine.served_paper import build_served_paper


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


@dataclass
class VersionedQuiz:
    """A one-question quiz with version 1 saved and a paper served on it."""

    form: Form
    question: FormQuestion
    right: QuestionOption
    wrong: QuestionOption
    paper: ServedPaper


def versioned_quiz() -> VersionedQuiz:
    """A quiz whose question reads "Original wording" with `right` as its correct
    option, saved as version 1, with the paper a sitting started now is served."""
    form: Form = FormFactory(strategy=FormStrategy.QUIZ, quiz_show_incorrect=True)
    page = FormPageFactory(form=form, order=0)
    question: FormQuestion = FormQuestionFactory(
        form_page=page,
        type="multiple_choice",
        order=0,
        question="Original wording",
    )
    right: QuestionOption = QuestionOptionFactory(
        question=question, text="Original right", correct=True, order=0
    )
    wrong: QuestionOption = QuestionOptionFactory(
        question=question, text="Original wrong", correct=False, order=1
    )
    save_question_version(question, list(question.options.all()), "c1")
    paper = build_served_paper(Form.objects.get(pk=form.pk))
    return VersionedQuiz(form, question, right, wrong, paper)


def revise_to_version_two(quiz: VersionedQuiz) -> FormQuestionVersion:
    """Reword the question and make the other option the correct one."""
    return revise_question(
        quiz.question,
        question="Revised wording",
        options=[
            {"id": quiz.right.id, "text": "Revised wrong", "correct": False},
            {"id": quiz.wrong.id, "text": "Revised right", "correct": True},
        ],
    )
