"""A topic or course part stays while any question names it."""

from __future__ import annotations

import pytest

from django.db import transaction
from django.db.models import ProtectedError

from freedom_ls.content_engine.factories import CoursePartFactory, TopicFactory
from freedom_ls.content_engine.models import CoursePart, Topic
from freedom_ls.form_engine.factories import FormQuestionFactory

pytestmark = pytest.mark.django_db


def test_deleting_a_topic_a_question_names_raises_protected_error(mock_site_context):
    topic = TopicFactory()
    question = FormQuestionFactory()
    question.topics.add(topic)

    with pytest.raises(ProtectedError), transaction.atomic():
        topic.delete()

    assert Topic.objects.filter(pk=topic.pk).exists()


def test_deleting_a_course_part_a_question_names_raises_protected_error(
    mock_site_context,
):
    part = CoursePartFactory()
    question = FormQuestionFactory()
    question.course_parts.add(part)

    with pytest.raises(ProtectedError), transaction.atomic():
        part.delete()

    assert CoursePart.objects.filter(pk=part.pk).exists()


def test_deleting_a_topic_no_question_names_succeeds(mock_site_context):
    topic = TopicFactory()

    topic.delete()

    assert not Topic.objects.filter(pk=topic.pk).exists()
