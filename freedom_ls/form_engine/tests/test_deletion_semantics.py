"""QuestionAnswer.question is PROTECTed against FormQuestion deletion."""

from __future__ import annotations

import pytest

from django.db import transaction
from django.db.models import ProtectedError

from freedom_ls.form_engine.factories import QuestionAnswerFactory

pytestmark = pytest.mark.django_db


def test_deleting_a_form_question_with_an_answer_is_blocked(mock_site_context):
    answer = QuestionAnswerFactory()

    with pytest.raises(ProtectedError), transaction.atomic():
        answer.question.delete()
