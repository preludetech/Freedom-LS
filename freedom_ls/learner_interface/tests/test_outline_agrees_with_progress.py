"""The course outline and the stored percentage agree on what a placement's status is.

Two read paths used to answer "is this form placement done" from different
sittings: the outline read the latest *started* attempt, while the percentage and
the finish page read the latest *completed* one. A learner who passed a quiz and
then began a retry they never finished put an open attempt at the head of the
outline's ordering, so the outline called the placement unfinished -- and, because
the outline is what the player gates on, re-locked the rest of a course they had
already unlocked -- while the percentage beside it still counted it done.
"""

import pytest

from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import FormStrategy
from freedom_ls.learner_interface.utils import get_course_index, outstanding_items
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory

from .conftest import course_progress_record, form_attempt, topic_completion

COURSE_SLUG = "retry-course"


@pytest.fixture
def retry_course(mock_site_context) -> dict:
    """topic_intro (1) -> quiz (2, pass 80) -> topic_after (3)."""
    course = CourseFactory(title="Retry Course", slug=COURSE_SLUG)
    topic_intro = TopicFactory(title="Intro", slug="retry-intro", content="intro")
    quiz = FormFactory(
        title="Retry quiz",
        slug="retry-quiz",
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=80,
    )
    topic_after = TopicFactory(title="After", slug="retry-after", content="after")
    course.items.create(child=topic_intro, order=0)
    course.items.create(child=quiz, order=1)
    course.items.create(child=topic_after, order=2)

    page = FormPageFactory(form=quiz, order=0)
    question = FormQuestionFactory(form_page=page, type="checkboxes", order=0)
    right = QuestionOptionFactory(question=question, correct=True, order=0)
    wrong = QuestionOptionFactory(question=question, correct=False, order=1)

    return {
        "course": course,
        "topic_intro": topic_intro,
        "quiz": quiz,
        "right": right,
        "wrong": wrong,
        "topic_after": topic_after,
    }


@pytest.fixture
def learner(mock_site_context, retry_course, client):
    user = UserFactory()
    LearnerCourseRegistrationFactory(
        learner__user=user, collection=retry_course["course"]
    )
    client.force_login(user)
    return user


def _sit_quiz(user, retry_course: dict, *, correct: bool) -> None:
    """One completed sitting of the quiz, scored by the real marker."""
    option = retry_course["right" if correct else "wrong"]
    attempt = form_attempt(retry_course["course"], user, retry_course["quiz"])
    answer = QuestionAnswerFactory(form_progress=attempt, question=option.question)
    answer.selected_options.add(option)
    attempt.complete()


def _begin_retry(user, retry_course: dict) -> None:
    """A fresh sitting the learner walks away from without finishing."""
    form_attempt(retry_course["course"], user, retry_course["quiz"])


def _statuses(user, retry_course: dict) -> list[str]:
    return [
        child["status"]
        for child in get_course_index(
            user=user, course=retry_course["course"], can_access_content=True
        )
    ]


# --- the reported bug ---------------------------------------------------------


@pytest.mark.django_db
def test_an_abandoned_retry_leaves_a_passed_quiz_complete_in_the_outline(
    retry_course, learner
):
    # Arrange
    topic_completion(
        retry_course["course"],
        learner,
        retry_course["topic_intro"],
        complete_time=timezone.now(),
    )
    _sit_quiz(learner, retry_course, correct=True)

    # Act
    _begin_retry(learner, retry_course)

    # Assert
    assert _statuses(learner, retry_course) == ["COMPLETE", "COMPLETE", "READY"]


@pytest.mark.django_db
def test_an_abandoned_retry_does_not_relock_the_item_after_a_passed_quiz(
    retry_course, learner, client
):
    """The outline is what the player gates on, so a re-lock is a real lockout."""
    # Arrange
    topic_completion(
        retry_course["course"],
        learner,
        retry_course["topic_intro"],
        complete_time=timezone.now(),
    )
    _sit_quiz(learner, retry_course, correct=True)
    _begin_retry(learner, retry_course)

    # Act
    response = client.get(
        reverse(
            "learner_interface:view_course_item",
            kwargs={"course_slug": COURSE_SLUG, "index": 3},
        )
    )

    # Assert
    assert response.status_code == 200


@pytest.mark.django_db
def test_the_outline_and_the_finish_page_agree_about_a_passed_quiz(
    retry_course, learner
):
    # Arrange
    topic_completion(
        retry_course["course"],
        learner,
        retry_course["topic_intro"],
        complete_time=timezone.now(),
    )
    _sit_quiz(learner, retry_course, correct=True)
    _begin_retry(learner, retry_course)
    record = course_progress_record(retry_course["course"], learner)
    record.refresh_from_db()

    # Act
    still_to_do = outstanding_items(record, retry_course["course"])

    # Assert
    quiz_status = _statuses(learner, retry_course)[1]
    assert quiz_status == "COMPLETE"
    assert [entry.content for entry in still_to_do] == [retry_course["topic_after"]]
    assert record.progress_percentage == 67


# --- the statuses this must not change ----------------------------------------


@pytest.mark.django_db
def test_a_first_sitting_still_in_flight_reads_in_progress(retry_course, learner):
    # Arrange / Act
    _begin_retry(learner, retry_course)

    # Assert
    assert _statuses(learner, retry_course)[1:] == ["IN_PROGRESS", "BLOCKED"]


@pytest.mark.django_db
def test_a_failed_sitting_still_reads_failed(retry_course, learner):
    # Arrange / Act
    _sit_quiz(learner, retry_course, correct=False)

    # Assert
    assert _statuses(learner, retry_course)[1:] == ["FAILED", "BLOCKED"]


@pytest.mark.django_db
def test_a_retry_of_a_failed_quiz_still_reads_in_progress(retry_course, learner):
    # Arrange
    _sit_quiz(learner, retry_course, correct=False)

    # Act
    _begin_retry(learner, retry_course)

    # Assert
    assert _statuses(learner, retry_course)[1:] == ["IN_PROGRESS", "BLOCKED"]


@pytest.mark.django_db
def test_a_pass_after_a_fail_still_reads_complete(retry_course, learner):
    # Arrange
    _sit_quiz(learner, retry_course, correct=False)

    # Act
    _sit_quiz(learner, retry_course, correct=True)

    # Assert
    assert _statuses(learner, retry_course)[1:] == ["COMPLETE", "READY"]


@pytest.mark.django_db
def test_an_abandoned_retry_of_a_form_with_no_pass_mark_still_reads_complete(
    mock_site_context,
):
    """A survey has no bar to clear, so finishing one is enough however often it is reopened."""
    # Arrange
    course = CourseFactory(title="Survey Course", slug="survey-course")
    survey = FormFactory(title="Survey", slug="survey", quiz_pass_percentage=None)
    topic_after = TopicFactory(title="After", slug="survey-after", content="after")
    course.items.create(child=survey, order=0)
    course.items.create(child=topic_after, order=1)
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, collection=course)
    form_attempt(course, user, survey, completed_time=timezone.now())

    # Act
    form_attempt(course, user, survey)

    # Assert
    children = get_course_index(user=user, course=course, can_access_content=True)
    assert [child["status"] for child in children] == ["COMPLETE", "READY"]
