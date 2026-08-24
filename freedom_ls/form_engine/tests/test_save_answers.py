"""``FormProgress.save_answers`` stores a row only for questions the learner
actually answered. A blank row would count toward the answered tally shown in
the runner, so an unanswered question must leave no row behind — and removing a
previously given answer must take its row with it.
"""

from __future__ import annotations

import pytest

from django.http import QueryDict

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import FormQuestion


def _post_data(pairs: dict[str, list[str]]) -> QueryDict:
    """Build a QueryDict the way a browser form submission would arrive."""
    data = QueryDict(mutable=True)
    for name, values in pairs.items():
        data.setlist(name, values)
    return data


@pytest.fixture
def choice_question(mock_site_context) -> FormQuestion:
    form = FormFactory()
    page = FormPageFactory(form=form, order=0)
    question: FormQuestion = FormQuestionFactory(
        form_page=page, type="multiple_choice", order=0
    )
    QuestionOptionFactory(question=question, text="Alpha", order=0)
    QuestionOptionFactory(question=question, text="Beta", order=1)
    return question


@pytest.fixture
def text_question(mock_site_context) -> FormQuestion:
    form = FormFactory()
    page = FormPageFactory(form=form, order=0)
    question: FormQuestion = FormQuestionFactory(
        form_page=page, type="short_text", order=0
    )
    return question


@pytest.mark.django_db
def test_unanswered_choice_question_stores_no_answer_row(
    mock_site_context, choice_question
):
    form_progress = FormProgressFactory(
        user=UserFactory(), form=choice_question.form_page.form
    )

    form_progress.save_answers([choice_question], _post_data({}))

    assert form_progress.answers.count() == 0


@pytest.mark.django_db
def test_blank_text_question_stores_no_answer_row(mock_site_context, text_question):
    form_progress = FormProgressFactory(
        user=UserFactory(), form=text_question.form_page.form
    )

    form_progress.save_answers(
        [text_question], _post_data({f"question_{text_question.id}": ["   "]})
    )

    assert form_progress.answers.count() == 0


@pytest.mark.django_db
def test_answered_choice_question_stores_the_selected_option(
    mock_site_context, choice_question
):
    form_progress = FormProgressFactory(
        user=UserFactory(), form=choice_question.form_page.form
    )
    option = choice_question.options.first()

    form_progress.save_answers(
        [choice_question],
        _post_data({f"question_{choice_question.id}": [str(option.id)]}),
    )

    answer = form_progress.answers.get(question=choice_question)
    assert list(answer.selected_options.all()) == [option]


@pytest.mark.django_db
def test_removing_a_choice_answer_clears_the_stored_row(
    mock_site_context, choice_question
):
    form_progress = FormProgressFactory(
        user=UserFactory(), form=choice_question.form_page.form
    )
    option = choice_question.options.first()
    form_progress.save_answers(
        [choice_question],
        _post_data({f"question_{choice_question.id}": [str(option.id)]}),
    )

    form_progress.save_answers([choice_question], _post_data({}))

    assert form_progress.answers.count() == 0


@pytest.mark.django_db
def test_removing_a_text_answer_clears_the_stored_row(mock_site_context, text_question):
    form_progress = FormProgressFactory(
        user=UserFactory(), form=text_question.form_page.form
    )
    form_progress.save_answers(
        [text_question], _post_data({f"question_{text_question.id}": ["Ohm's law"]})
    )

    form_progress.save_answers(
        [text_question], _post_data({f"question_{text_question.id}": [""]})
    )

    assert form_progress.answers.count() == 0


@pytest.mark.django_db
def test_changing_a_choice_answer_replaces_the_previous_selection(
    mock_site_context, choice_question
):
    form_progress = FormProgressFactory(
        user=UserFactory(), form=choice_question.form_page.form
    )
    first, second = list(choice_question.options.all())
    form_progress.save_answers(
        [choice_question],
        _post_data({f"question_{choice_question.id}": [str(first.id)]}),
    )

    form_progress.save_answers(
        [choice_question],
        _post_data({f"question_{choice_question.id}": [str(second.id)]}),
    )

    answer = form_progress.answers.get(question=choice_question)
    assert list(answer.selected_options.all()) == [second]
