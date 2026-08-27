"""Tests for which page a FormProgress attempt resumes on."""

from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.factories import (
    FormContentFactory,
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
)
from freedom_ls.form_engine.models import Form, FormPage, FormProgress, FormQuestion


def _page_with_question(form: Form, order: int) -> tuple[FormPage, FormQuestion]:
    """One page carrying a single short-text question."""
    page: FormPage = FormPageFactory(form=form, title=f"Page {order + 1}", order=order)
    question: FormQuestion = FormQuestionFactory(
        form_page=page, question=f"Question {order + 1}", type="short_text", order=0
    )
    return page, question


@pytest.mark.django_db
def test_get_current_page_number_no_answers(mock_site_context):
    """An attempt with nothing answered resumes on the first page."""
    form = FormFactory()
    _page_with_question(form, order=0)
    _page_with_question(form, order=1)

    form_progress: FormProgress = FormProgressFactory(user=UserFactory(), form=form)

    assert form_progress.get_current_page_number() == 1


@pytest.mark.django_db
def test_get_current_page_number_partially_answered(mock_site_context):
    """An attempt resumes on the first page still holding an unanswered question."""
    form = FormFactory()
    _page, question_1 = _page_with_question(form, order=0)
    _page_with_question(form, order=1)
    _page_with_question(form, order=2)

    form_progress: FormProgress = FormProgressFactory(user=UserFactory(), form=form)
    QuestionAnswerFactory(
        form_progress=form_progress, question=question_1, text_answer="Answer 1"
    )

    assert form_progress.get_current_page_number() == 2


@pytest.mark.django_db
def test_get_current_page_number_all_answered(mock_site_context):
    """With every question answered, the attempt resumes on the last page."""
    form = FormFactory()
    _page_1, question_1 = _page_with_question(form, order=0)
    _page_2, question_2 = _page_with_question(form, order=1)

    form_progress: FormProgress = FormProgressFactory(user=UserFactory(), form=form)
    QuestionAnswerFactory(
        form_progress=form_progress, question=question_1, text_answer="Answer 1"
    )
    QuestionAnswerFactory(
        form_progress=form_progress, question=question_2, text_answer="Answer 2"
    )

    assert form_progress.get_current_page_number() == 2


@pytest.mark.django_db
def test_get_current_page_number_page_with_text_only(mock_site_context):
    """A page carrying only content has nothing to answer, so it is not resumed on."""
    form = FormFactory()
    text_only_page = FormPageFactory(form=form, title="Page 1", order=0)
    FormContentFactory(form_page=text_only_page, content="Intro text", order=0)
    _page_with_question(form, order=1)

    form_progress: FormProgress = FormProgressFactory(user=UserFactory(), form=form)

    assert form_progress.get_current_page_number() == 2
