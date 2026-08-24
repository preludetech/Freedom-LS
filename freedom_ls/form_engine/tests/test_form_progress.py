"""Tests for FormProgress page tracking and attempt reuse."""

from __future__ import annotations

from datetime import timedelta

import pytest

from django.utils import timezone

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


@pytest.mark.django_db
def test_get_or_create_incomplete_no_existing(mock_site_context):
    """A learner with no attempt at the form gets a fresh incomplete one."""
    user = UserFactory()
    form = FormFactory()

    progress = FormProgress.get_or_create_incomplete(user, form)

    assert progress.user == user
    assert progress.form == form
    assert progress.completed_time is None
    assert FormProgress.objects.filter(user=user, form=form).count() == 1


@pytest.mark.django_db
def test_get_or_create_incomplete_returns_existing_incomplete(
    mock_site_context,
):
    """An attempt already under way is resumed rather than replaced."""
    user = UserFactory()
    form = FormFactory()
    existing: FormProgress = FormProgressFactory(user=user, form=form)

    progress = FormProgress.get_or_create_incomplete(user, form)

    assert progress.id == existing.id
    assert FormProgress.objects.filter(user=user, form=form).count() == 1


@pytest.mark.django_db
def test_get_or_create_incomplete_creates_new_when_completed(
    mock_site_context,
):
    """A finished attempt is left alone; re-sitting the form starts a new one."""
    user = UserFactory()
    form = FormFactory()
    completed: FormProgress = FormProgressFactory(
        user=user, form=form, completed_time=timezone.now()
    )

    progress = FormProgress.get_or_create_incomplete(user, form)

    assert progress.id != completed.id
    assert progress.completed_time is None
    assert FormProgress.objects.filter(user=user, form=form).count() == 2


@pytest.mark.django_db
def test_get_or_create_incomplete_returns_latest_incomplete(
    mock_site_context,
):
    """Where two incomplete attempts exist, the most recently started one wins."""
    user = UserFactory()
    form = FormFactory()
    older: FormProgress = FormProgressFactory(user=user, form=form)
    FormProgress.objects.filter(pk=older.pk).update(
        start_time=timezone.now() - timedelta(seconds=10)
    )
    newer: FormProgress = FormProgressFactory(user=user, form=form)

    progress = FormProgress.get_or_create_incomplete(user, form)

    assert progress.id == newer.id
    assert FormProgress.objects.filter(user=user, form=form).count() == 2
