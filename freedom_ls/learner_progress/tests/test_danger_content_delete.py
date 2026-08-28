"""Content deletion against PROTECTed progress rows."""

from __future__ import annotations

import pytest

from django.core.management import call_command
from django.db import transaction
from django.db.models import ProtectedError

from freedom_ls.content_engine.models import Course, Topic
from freedom_ls.form_engine.factories import QuestionAnswerFactory
from freedom_ls.form_engine.models import FormQuestion, QuestionAnswer
from freedom_ls.learner_progress.factories import TopicProgressFactory
from freedom_ls.learner_progress.models import CourseProgress, TopicProgress

pytestmark = pytest.mark.django_db


def test_danger_content_delete_succeeds_with_progress_rows_present(mock_site_context):
    TopicProgressFactory()

    call_command("danger_content_delete", "--yes")

    assert Topic.objects.count() == 0
    assert Course.objects.count() == 0
    assert TopicProgress.objects.count() == 0
    assert CourseProgress.objects.count() == 0


def test_deleting_a_topic_with_progress_is_blocked(mock_site_context):
    """PROTECT, so a content delete by any other route loses no completion."""
    progress = TopicProgressFactory()

    with pytest.raises(ProtectedError), transaction.atomic():
        progress.topic.delete()


def test_danger_content_delete_succeeds_with_question_answers_present(
    mock_site_context,
):
    """QuestionAnswer.question is PROTECTed; the command clears answers first."""
    QuestionAnswerFactory()

    call_command("danger_content_delete", "--yes")

    assert FormQuestion.objects.count() == 0
    assert QuestionAnswer.objects.count() == 0
