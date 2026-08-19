"""A learner has to pass to complete a course, so the finish page must not stamp
a completion over a quiz they sat and failed."""

from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.student_progress.factories import CourseProgressFactory
from freedom_ls.student_progress.models import CourseProgress


def _finish(client, user, course):
    client.force_login(user)
    return client.get(
        reverse("student_interface:course_finish", kwargs={"course_slug": course.slug})
    )


@pytest.mark.django_db
def test_finish_page_does_not_complete_a_course_with_a_failed_quiz(
    mock_site_context, client, course_with_scored_quiz, sit_quiz
):
    """A learner who failed the course's quiz is not marked as having completed it."""
    user = UserFactory()
    course, form, question, _right, wrong = course_with_scored_quiz(
        slug="finish-failed"
    )
    progress: CourseProgress = CourseProgressFactory(
        user=user, course=course, completed_time=None
    )
    sit_quiz(user, form, question, wrong)

    _finish(client, user, course)

    progress.refresh_from_db()
    assert progress.completed_time is None


@pytest.mark.django_db
def test_finish_page_completes_a_course_once_the_quiz_is_passed(
    mock_site_context, client, course_with_scored_quiz, sit_quiz
):
    """Passing the retry lets the finish page record the completion."""
    user = UserFactory()
    course, form, question, right, wrong = course_with_scored_quiz(slug="finish-passed")
    progress: CourseProgress = CourseProgressFactory(
        user=user, course=course, completed_time=None
    )
    sit_quiz(user, form, question, wrong)
    sit_quiz(user, form, question, right)

    _finish(client, user, course)

    progress.refresh_from_db()
    assert progress.completed_time is not None


@pytest.mark.django_db
def test_finish_page_still_renders_for_a_course_with_a_failed_quiz(
    mock_site_context, client, course_with_scored_quiz, sit_quiz
):
    """Withholding the completion must not take the page away from the learner."""
    user = UserFactory()
    course, form, question, _right, wrong = course_with_scored_quiz(
        slug="finish-renders"
    )
    CourseProgressFactory(user=user, course=course, completed_time=None)
    sit_quiz(user, form, question, wrong)

    response = _finish(client, user, course)

    assert response.status_code == 200


@pytest.mark.django_db
def test_finish_page_names_the_unpassed_quiz_and_links_to_its_retry(
    mock_site_context, client, course_with_scored_quiz, sit_quiz
):
    """A withheld completion has to say what is left, not congratulate the learner."""
    user = UserFactory()
    course, form, question, _right, wrong = course_with_scored_quiz(slug="finish-names")
    CourseProgressFactory(user=user, course=course, completed_time=None)
    sit_quiz(user, form, question, wrong)

    content = _finish(client, user, course).content.decode()

    assert "Congratulations" not in content
    assert "pass the quiz below" in content  # one quiz, so no "quizzes"
    assert form.title in content
    assert (
        reverse(
            "student_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
        in content
    )


@pytest.mark.django_db
def test_finish_page_congratulates_once_the_quiz_is_passed(
    mock_site_context, client, course_with_scored_quiz, sit_quiz
):
    """Passing the retry earns the completion copy and the completion date."""
    user = UserFactory()
    course, form, question, right, wrong = course_with_scored_quiz(
        slug="finish-congratulates"
    )
    CourseProgressFactory(user=user, course=course, completed_time=None)
    sit_quiz(user, form, question, wrong)
    sit_quiz(user, form, question, right)

    content = _finish(client, user, course).content.decode()

    assert "Congratulations" in content
    assert 'data-testid="unpassed-forms"' not in content
    assert "Completed:" in content
