"""Tests for student_progress factories."""

import pytest
from django.contrib.sites.models import Site

from freedom_ls.student_progress.factories import (
    CourseProgressFactory,
    FormProgressFactory,
    QuestionAnswerFactory,
    TopicProgressFactory,
)
from freedom_ls.student_progress.models import (
    CourseProgress,
    FormProgress,
    QuestionAnswer,
    TopicProgress,
)


@pytest.mark.django_db
class TestCourseProgressFactory:
    def test_creates_valid_instance(self, mock_site_context: Site) -> None:
        progress = CourseProgressFactory()
        assert isinstance(progress, CourseProgress)
        assert progress.pk is not None

    def test_user_subfactory(self, mock_site_context: Site) -> None:
        progress = CourseProgressFactory()
        assert progress.user is not None
        assert progress.user.pk is not None

    def test_course_subfactory(self, mock_site_context: Site) -> None:
        progress = CourseProgressFactory()
        assert progress.course is not None
        assert progress.course.pk is not None

    def test_default_progress_percentage(self, mock_site_context: Site) -> None:
        progress = CourseProgressFactory()
        assert progress.progress_percentage == 0

    def test_site_set_from_context(self, mock_site_context: Site) -> None:
        progress = CourseProgressFactory()
        assert progress.site == mock_site_context


@pytest.mark.django_db
class TestTopicProgressFactory:
    def test_creates_valid_instance(self, mock_site_context: Site) -> None:
        progress = TopicProgressFactory()
        assert isinstance(progress, TopicProgress)
        assert progress.pk is not None

    def test_user_subfactory(self, mock_site_context: Site) -> None:
        progress = TopicProgressFactory()
        assert progress.user is not None
        assert progress.user.pk is not None

    def test_topic_subfactory(self, mock_site_context: Site) -> None:
        progress = TopicProgressFactory()
        assert progress.topic is not None
        assert progress.topic.pk is not None

    def test_complete_time_defaults_to_none(self, mock_site_context: Site) -> None:
        progress = TopicProgressFactory()
        assert progress.complete_time is None

    def test_site_set_from_context(self, mock_site_context: Site) -> None:
        progress = TopicProgressFactory()
        assert progress.site == mock_site_context


@pytest.mark.django_db
class TestFormProgressFactory:
    def test_creates_valid_instance(self, mock_site_context: Site) -> None:
        progress = FormProgressFactory()
        assert isinstance(progress, FormProgress)
        assert progress.pk is not None

    def test_user_subfactory(self, mock_site_context: Site) -> None:
        progress = FormProgressFactory()
        assert progress.user is not None
        assert progress.user.pk is not None

    def test_form_subfactory(self, mock_site_context: Site) -> None:
        progress = FormProgressFactory()
        assert progress.form is not None
        assert progress.form.pk is not None

    def test_completed_time_defaults_to_none(self, mock_site_context: Site) -> None:
        progress = FormProgressFactory()
        assert progress.completed_time is None

    def test_scores_defaults_to_none(self, mock_site_context: Site) -> None:
        progress = FormProgressFactory()
        assert progress.scores is None

    def test_site_set_from_context(self, mock_site_context: Site) -> None:
        progress = FormProgressFactory()
        assert progress.site == mock_site_context


@pytest.mark.django_db
class TestQuestionAnswerFactory:
    def test_creates_valid_instance(self, mock_site_context: Site) -> None:
        answer = QuestionAnswerFactory()
        assert isinstance(answer, QuestionAnswer)
        assert answer.pk is not None

    def test_form_progress_subfactory(self, mock_site_context: Site) -> None:
        answer = QuestionAnswerFactory()
        assert answer.form_progress is not None
        assert answer.form_progress.pk is not None

    def test_question_subfactory(self, mock_site_context: Site) -> None:
        answer = QuestionAnswerFactory()
        assert answer.question is not None
        assert answer.question.pk is not None

    def test_text_answer_defaults_to_none(self, mock_site_context: Site) -> None:
        answer = QuestionAnswerFactory()
        assert answer.text_answer is None

    def test_site_set_from_context(self, mock_site_context: Site) -> None:
        answer = QuestionAnswerFactory()
        assert answer.site == mock_site_context
