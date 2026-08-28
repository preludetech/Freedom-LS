"""A course is complete when every item in it is, so the finish page must not stamp
a completion while any topic is unread or any quiz is unpassed -- one never sat as
much as one sat and failed."""

from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.form_engine.models import FormProgress
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseFormAttempt, CourseProgress


def _finish(client, user, course):
    client.force_login(user)
    return client.get(
        reverse("learner_interface:course_finish", kwargs={"course_slug": course.slug})
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
        learner__user=user, course=course, completed_time=None
    )
    sit_quiz(progress, form, question, wrong)

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
        learner__user=user, course=course, completed_time=None
    )
    sit_quiz(progress, form, question, wrong)
    sit_quiz(progress, form, question, right)

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
    progress: CourseProgress = CourseProgressFactory(
        learner__user=user, course=course, completed_time=None
    )
    sit_quiz(progress, form, question, wrong)

    response = _finish(client, user, course)

    assert response.status_code == 200


@pytest.mark.django_db
def test_finish_page_names_the_unpassed_quiz_and_links_to_its_retry(
    mock_site_context, client, course_with_scored_quiz, sit_quiz
):
    """A withheld completion has to say what is left, not congratulate the learner."""
    user = UserFactory()
    course, form, question, _right, wrong = course_with_scored_quiz(slug="finish-names")
    progress: CourseProgress = CourseProgressFactory(
        learner__user=user, course=course, completed_time=None
    )
    sit_quiz(progress, form, question, wrong)

    content = _finish(client, user, course).content.decode()

    assert "Congratulations" not in content
    assert "finish the item below" in content  # one item, so no "items"
    assert form.title in content
    assert "Retry quiz" in content
    assert (
        reverse(
            "learner_interface:form_start",
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
    progress: CourseProgress = CourseProgressFactory(
        learner__user=user, course=course, completed_time=None
    )
    sit_quiz(progress, form, question, wrong)
    sit_quiz(progress, form, question, right)

    content = _finish(client, user, course).content.decode()

    assert "Congratulations" in content
    assert 'data-testid="outstanding-items"' not in content
    assert "Completed:" in content


@pytest.mark.django_db
def test_finish_page_does_not_complete_a_course_with_a_never_sat_quiz(
    mock_site_context, client, course_with_scored_quiz
):
    """A quiz the learner never opened withholds the completion as firmly as one they failed."""
    user = UserFactory()
    course, _form, _question, _right, _wrong = course_with_scored_quiz(
        slug="finish-never-sat"
    )
    progress: CourseProgress = CourseProgressFactory(
        learner__user=user, course=course, completed_time=None
    )

    _finish(client, user, course)

    progress.refresh_from_db()
    assert progress.completed_time is None


@pytest.mark.django_db
def test_finish_page_does_not_complete_a_course_with_an_unread_topic(
    mock_site_context, client
):
    """Completion counts every item, not only the quizzes."""
    user = UserFactory()
    course = CourseFactory(title="Unread", slug="finish-unread-topic")
    topic = TopicFactory(title="Key Ideas", slug="finish-key-ideas", content="x")
    course.items.create(child=topic, order=0)
    progress: CourseProgress = CourseProgressFactory(
        learner__user=user, course=course, completed_time=None
    )

    _finish(client, user, course)

    progress.refresh_from_db()
    assert progress.completed_time is None


@pytest.mark.django_db
def test_finish_page_names_a_never_sat_quiz_and_offers_to_start_it(
    mock_site_context, client, course_with_scored_quiz
):
    """A quiz never sat is offered as a start, not as a retry of nothing.

    It is offered through the read-only start screen rather than form_start,
    which mints an attempt on GET -- see the test below.
    """
    user = UserFactory()
    course, form, _question, _right, _wrong = course_with_scored_quiz(
        slug="finish-start-quiz"
    )
    CourseProgressFactory(learner__user=user, course=course, completed_time=None)

    content = _finish(client, user, course).content.decode()

    assert "Congratulations" not in content
    assert form.title in content
    assert "Start quiz" in content
    assert "Retry quiz" not in content
    assert (
        reverse(
            "learner_interface:view_course_item",
            kwargs={"course_slug": course.slug, "index": 1},
        )
        in content
    )


@pytest.mark.django_db
def test_the_offer_to_start_a_quiz_does_not_go_through_a_writing_view(
    mock_site_context, client, course_with_scored_quiz
):
    """Following the offer must not sit the quiz on the learner's behalf.

    form_start mints a FormProgress and a CourseFormAttempt on GET, so
    offering it for a quiz never sat would let merely following the link and
    backing out leave an empty attempt behind -- which a submit-on-exit form
    later finalises into a zero-score sitting the learner never took.
    """
    user = UserFactory()
    course, form, _question, _right, _wrong = course_with_scored_quiz(
        slug="finish-start-quiz-no-write"
    )
    CourseProgressFactory(learner__user=user, course=course, completed_time=None)

    response = _finish(client, user, course)
    offered = response.context["outstanding_items"][0].url
    client.get(offered)

    assert not FormProgress.objects.filter(form=form).exists()
    assert not CourseFormAttempt.objects.exists()


@pytest.mark.django_db
def test_finish_page_names_an_unread_topic_and_links_to_it(mock_site_context, client):
    """An outstanding topic is named and linked, the same as an outstanding quiz."""
    user = UserFactory()
    course = CourseFactory(title="Unread", slug="finish-names-topic")
    topic = TopicFactory(title="Going Deeper", slug="finish-going-deeper", content="x")
    course.items.create(child=topic, order=0)
    CourseProgressFactory(learner__user=user, course=course, completed_time=None)

    content = _finish(client, user, course).content.decode()

    assert "Congratulations" not in content
    assert topic.title in content
    assert (
        reverse(
            "learner_interface:view_course_item",
            kwargs={"course_slug": course.slug, "index": 1},
        )
        in content
    )


@pytest.mark.django_db
def test_finish_page_offers_to_start_an_unfinished_survey(mock_site_context, client):
    """A form with no pass mark is started, not retried and not "passed"."""
    from .conftest import course_with_single_question_form

    user = UserFactory()
    course = course_with_single_question_form("Survey", "finish-survey")
    CourseProgressFactory(learner__user=user, course=course, completed_time=None)

    content = _finish(client, user, course).content.decode()

    assert "Congratulations" not in content
    assert "Start form" in content
    assert "Start quiz" not in content
