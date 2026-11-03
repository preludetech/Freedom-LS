"""Receivers connected by the form_engine app."""

from __future__ import annotations

import pytest

from django.db import transaction

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionAnswerFileFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import FormProgress, QuestionAnswerFile


@pytest.fixture
def off_path_file_answer(mock_site_context) -> QuestionAnswerFile:
    """A sitting whose only file answer belongs to a page that "no" closes."""
    form = FormFactory()
    page_one = FormPageFactory(form=form, order=0)
    gate = FormQuestionFactory(form_page=page_one, type="multiple_choice", order=0)
    yes = QuestionOptionFactory(question=gate, value="yes", order=0)
    no = QuestionOptionFactory(question=gate, value="no", order=1)
    page_two = FormPageFactory(form=form, order=1, condition_option=yes)
    upload = FormQuestionFactory(form_page=page_two, type="file_upload", order=0)
    progress = FormProgressFactory(form=form, user=UserFactory())
    QuestionAnswerFactory(form_progress=progress, question=gate).selected_options.set(
        [no]
    )
    answer = QuestionAnswerFactory(form_progress=progress, question=upload)
    answer_file: QuestionAnswerFile = QuestionAnswerFileFactory(answer=answer)
    return answer_file


@pytest.mark.django_db
def test_completing_removes_the_stored_file_of_an_off_path_answer(
    off_path_file_answer, django_capture_on_commit_callbacks
):
    storage, name = off_path_file_answer.file.storage, off_path_file_answer.file.name

    with django_capture_on_commit_callbacks(execute=True):
        off_path_file_answer.answer.form_progress.complete()

    assert storage.exists(name) is False


class _RollbackError(Exception):
    pass


def _complete_then_roll_back(progress: FormProgress) -> None:
    with transaction.atomic():
        progress.complete()
        raise _RollbackError


@pytest.mark.django_db
def test_a_rolled_back_completion_keeps_the_stored_file(
    off_path_file_answer, django_capture_on_commit_callbacks
):
    storage, name = off_path_file_answer.file.storage, off_path_file_answer.file.name
    progress = off_path_file_answer.answer.form_progress

    with (
        django_capture_on_commit_callbacks(execute=True),
        pytest.raises(_RollbackError),
    ):
        _complete_then_roll_back(progress)

    assert storage.exists(name) is True
