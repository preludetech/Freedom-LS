"""Fixtures for a course that holds a scored quiz, and for sitting that quiz.

Shared by the learner_progress and learner_interface tests, whose conftests import
them by name.
"""

from collections.abc import Callable

import pytest

from django.contrib.sites.models import Site

from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
)
from freedom_ls.content_engine.models import ContentCollectionItem, Course
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import (
    Form,
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionAnswer,
    QuestionOption,
)
from freedom_ls.learner_progress.factories import CourseFormAttemptFactory
from freedom_ls.learner_progress.models import CourseProgress

ScoredQuiz = tuple[Course, Form, FormQuestion, QuestionOption, QuestionOption]


@pytest.fixture
def course_with_scored_quiz(mock_site_context: Site) -> Callable[..., ScoredQuiz]:
    """Factory: a course holding one two-option quiz a learner can pass or fail on demand.

    Returns (course, form, question, right_option, wrong_option). Pass
    ``pass_percentage=None`` for a quiz with no bar to clear.
    """

    def _make(
        *, pass_percentage: int | None = 80, **course_kwargs: object
    ) -> ScoredQuiz:
        course: Course = CourseFactory(**course_kwargs)
        form: Form = FormFactory(
            strategy=FormStrategy.QUIZ, quiz_pass_percentage=pass_percentage
        )
        ContentCollectionItemFactory(
            collection_object=course, child_object=form, order=0
        )
        page = FormPageFactory(form=form, title="Quiz Page 1", order=0)
        question: FormQuestion = FormQuestionFactory(
            form_page=page, question="What is 2 + 2?", type="multiple_choice", order=0
        )
        right: QuestionOption = QuestionOptionFactory(
            question=question, text="4", value="4", order=0, correct=True
        )
        wrong: QuestionOption = QuestionOptionFactory(
            question=question, text="3", value="3", order=1, correct=False
        )
        return course, form, question, right, wrong

    return _make


@pytest.fixture
def sit_quiz() -> Callable[
    [CourseProgress, Form, FormQuestion, QuestionOption], FormProgress
]:
    """Factory: complete one attempt at `form` within `course_progress`.

    The attempt is scoped to the collection item placing `form` in that
    record's course, so repeated sittings accumulate against one placement.
    """

    def _sit(
        course_progress: CourseProgress,
        form: Form,
        question: FormQuestion,
        option: QuestionOption,
    ) -> FormProgress:
        collection_item = ContentCollectionItem.objects.get(
            collection_id=course_progress.course_id, child_id=form.id
        )
        course_attempt = CourseFormAttemptFactory(
            course_progress=course_progress,
            collection_item=collection_item,
            form=form,
        )
        attempt: FormProgress = course_attempt.form_progress
        answer: QuestionAnswer = QuestionAnswerFactory(
            form_progress=attempt, question=question
        )
        answer.selected_options.add(option)
        attempt.complete()
        return attempt

    return _sit
