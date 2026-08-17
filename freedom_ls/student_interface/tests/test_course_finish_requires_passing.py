"""A learner has to pass to complete a course, so the finish page must not stamp
a completion over a quiz they sat and failed."""

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.student_progress.factories import (
    CourseProgressFactory,
    FormProgressFactory,
    QuestionAnswerFactory,
)
from freedom_ls.student_progress.models import CourseProgress, FormProgress


def _course_with_scored_quiz(slug: str):
    course = CourseFactory(slug=slug)
    form = FormFactory(strategy="QUIZ", quiz_pass_percentage=80)
    ContentCollectionItemFactory(collection_object=course, child_object=form, order=0)
    page = FormPageFactory(form=form, title="Quiz Page 1", order=0)
    question = FormQuestionFactory(
        form_page=page,
        question="What is 2 + 2?",
        type="multiple_choice",
        order=0,
    )
    right = QuestionOptionFactory(
        question=question, text="4", value="4", order=0, correct=True
    )
    wrong = QuestionOptionFactory(
        question=question, text="3", value="3", order=1, correct=False
    )
    return course, form, question, right, wrong


def _sit_quiz(user, form, question, option):
    attempt: FormProgress = FormProgressFactory(user=user, form=form)
    answer = QuestionAnswerFactory(form_progress=attempt, question=question)
    answer.selected_options.add(option)
    attempt.complete()


def _finish(user, course):
    client = Client()
    client.force_login(user)
    return client.get(
        reverse("student_interface:course_finish", kwargs={"course_slug": course.slug})
    )


@pytest.mark.django_db
def test_finish_page_does_not_complete_a_course_with_a_failed_quiz(mock_site_context):
    """A learner who failed the course's quiz is not marked as having completed it."""
    user = UserFactory()
    course, form, question, _right, wrong = _course_with_scored_quiz("finish-failed")
    progress: CourseProgress = CourseProgressFactory(
        user=user, course=course, completed_time=None
    )
    _sit_quiz(user, form, question, wrong)

    _finish(user, course)

    progress.refresh_from_db()
    assert progress.completed_time is None


@pytest.mark.django_db
def test_finish_page_completes_a_course_once_the_quiz_is_passed(mock_site_context):
    """Passing the retry lets the finish page record the completion."""
    user = UserFactory()
    course, form, question, right, wrong = _course_with_scored_quiz("finish-passed")
    progress: CourseProgress = CourseProgressFactory(
        user=user, course=course, completed_time=None
    )
    _sit_quiz(user, form, question, wrong)
    _sit_quiz(user, form, question, right)

    _finish(user, course)

    progress.refresh_from_db()
    assert progress.completed_time is not None


@pytest.mark.django_db
def test_finish_page_still_renders_for_a_course_with_a_failed_quiz(mock_site_context):
    """Withholding the completion must not take the page away from the learner."""
    user = UserFactory()
    course, form, question, _right, wrong = _course_with_scored_quiz("finish-renders")
    CourseProgressFactory(user=user, course=course, completed_time=None)
    _sit_quiz(user, form, question, wrong)

    response = _finish(user, course)

    assert response.status_code == 200
