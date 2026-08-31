"""Bulk progress deletion: the confirmation prompt and the deletion itself."""

from __future__ import annotations

from unittest import mock

import pytest

from django.core.management import call_command

from freedom_ls.content_engine.models import Course, Topic
from freedom_ls.form_engine.factories import QuestionAnswerFactory
from freedom_ls.form_engine.models import FormProgress, QuestionAnswer
from freedom_ls.learner_progress.factories import (
    CourseFormAttemptFactory,
    TopicProgressFactory,
)
from freedom_ls.learner_progress.models import (
    CourseFormAttempt,
    CourseProgress,
    TopicProgress,
)

pytestmark = pytest.mark.django_db


def test_yes_flag_empties_all_five_progress_tables_and_leaves_content_intact(
    mock_site_context,
):
    TopicProgressFactory()
    attempt = CourseFormAttemptFactory()
    QuestionAnswerFactory(form_progress=attempt.form_progress)
    course_count_before = Course.objects.count()
    topic_count_before = Topic.objects.count()

    call_command("danger_clear_all_course_progress", "--yes")

    assert QuestionAnswer.objects.count() == 0
    assert CourseFormAttempt.objects.count() == 0
    assert FormProgress.objects.count() == 0
    assert TopicProgress.objects.count() == 0
    assert CourseProgress.objects.count() == 0
    assert Course.objects.count() == course_count_before
    assert Topic.objects.count() == topic_count_before


def test_declining_the_prompt_deletes_nothing(mock_site_context):
    TopicProgressFactory()

    with mock.patch("djclick.confirm", return_value=False):
        call_command("danger_clear_all_course_progress")

    assert TopicProgress.objects.count() == 1
    assert CourseProgress.objects.count() == 1


def test_confirming_the_prompt_deletes_progress(mock_site_context):
    TopicProgressFactory()

    with mock.patch("djclick.confirm", return_value=True):
        call_command("danger_clear_all_course_progress")

    assert TopicProgress.objects.count() == 0
    assert CourseProgress.objects.count() == 0
