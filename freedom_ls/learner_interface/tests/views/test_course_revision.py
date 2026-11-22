"""The revision page: who may open it, the start screen and answering a session."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import time_machine

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.deadlines.factories import (
    CourseDeadlineConfigFactory,
    CoursePauseFactory,
)
from freedom_ls.learner_interface.tests.helpers import topic_completion
from freedom_ls.learner_progress.tests.helpers import course_progress_record
from freedom_ls.revision.factories import RevisionReviewFactory
from freedom_ls.revision.models import RevisionReview
from freedom_ls.revision.services import RevisionSessionState
from freedom_ls.revision.tests.helpers import (
    choice_question,
    finish_topic,
    place_topic,
    question_testing_topic,
)
from freedom_ls.tests.factories import SiteFactory


def _revision_url(course) -> str:
    return reverse(
        "learner_interface:course_revision", kwargs={"course_slug": course.slug}
    )


def _detail_url(course) -> str:
    return reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )


def _client_for(user) -> Client:
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_unregistered_learner_is_sent_to_the_course_detail_page(mock_site_context):
    course = CourseFactory()
    client = _client_for(UserFactory())

    response = client.get(_revision_url(course))

    assert response.status_code == 302
    assert response.url == _detail_url(course)


@pytest.mark.django_db
def test_paused_course_sends_the_learner_to_the_course_detail_page(
    mock_site_context,
):
    course = CourseFactory()
    user = UserFactory()
    CoursePauseFactory(course_progress=course_progress_record(course, user))

    response = _client_for(user).get(_revision_url(course))

    assert response.status_code == 302
    assert response.url == _detail_url(course)


@pytest.mark.django_db
@time_machine.travel(datetime(2026, 9, 1, 10, 0, tzinfo=UTC), tick=False)
def test_ended_registration_sends_the_learner_to_the_course_detail_page(
    mock_site_context,
):
    course = CourseFactory(time_limit_days=30)
    CourseDeadlineConfigFactory(course=course, end_course_access="on")
    user = UserFactory()
    course_progress_record(
        course, user, created_at=datetime(2026, 3, 1, 10, 0, tzinfo=UTC)
    )

    response = _client_for(user).get(_revision_url(course))

    assert response.status_code == 302
    assert response.url == _detail_url(course)


@pytest.mark.django_db
def test_course_on_another_site_is_not_found(mock_site_context):
    course = CourseFactory(site=SiteFactory())
    client = _client_for(UserFactory())

    response = client.get(_revision_url(course))

    assert response.status_code == 404


@pytest.mark.django_db
def test_registered_learner_sees_the_count_of_their_bank(mock_site_context):
    course = CourseFactory()
    finished = TopicFactory()
    unfinished = TopicFactory()
    course.items.create(child=finished, order=0)
    course.items.create(child=unfinished, order=1)
    question_testing_topic(finished)
    question_testing_topic(finished)
    question_testing_topic(unfinished)
    user = UserFactory()
    topic_completion(
        course, user, finished, complete_time=datetime(2026, 3, 2, tzinfo=UTC)
    )

    response = _client_for(user).get(_revision_url(course))

    assert response.status_code == 200
    assert "2 ready" in response.content.decode()


def _route_url(route: str, course) -> str:
    return reverse(f"learner_interface:{route}", kwargs={"course_slug": course.slug})


def _store_session(
    client: Client, course, questions, *, index: int = 0, started_at=None
):
    state = RevisionSessionState(
        question_ids=tuple(q.pk for q in questions),
        started_at=started_at or datetime(2026, 1, 1, tzinfo=UTC),
        index=index,
    )
    session = client.session
    session[f"revision_session:{course.id}"] = state.model_dump(mode="json")
    session.save()


def _stored_index(client: Client, course) -> int:
    return int(client.session[f"revision_session:{course.id}"]["index"])


def _banked_session(*, question_count: int = 1):
    """A learner who finished a topic with questions, logged in with a session over them."""
    course = CourseFactory()
    topic, _ = place_topic(course)
    questions = [question_testing_topic(topic) for _ in range(question_count)]
    user = UserFactory()
    finish_topic(course_progress_record(course, user), topic)
    client = _client_for(user)
    _store_session(client, course, questions)
    return course, user, questions, client


def _post_answer(client: Client, course, question, option_ids):
    return client.post(
        _route_url("course_revision_answer", course),
        {f"question_{question.id}": option_ids},
        HTTP_HX_REQUEST="true",
    )


def _right_option(question):
    return question.options.get(correct=True)


def _wrong_option(question):
    return question.options.get(correct=False)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "route", ["course_revision_start", "course_revision_answer", "course_revision_next"]
)
def test_post_routes_turn_away_an_unregistered_learner(route, mock_site_context):
    course = CourseFactory()
    client = _client_for(UserFactory())

    response = client.post(_route_url(route, course))

    assert (response.status_code, response.url) == (302, _detail_url(course))


@pytest.mark.django_db
@pytest.mark.parametrize(
    "route", ["course_revision_start", "course_revision_answer", "course_revision_next"]
)
def test_post_routes_turn_away_a_paused_course(route, mock_site_context):
    course = CourseFactory()
    user = UserFactory()
    CoursePauseFactory(course_progress=course_progress_record(course, user))

    response = _client_for(user).post(_route_url(route, course))

    assert (response.status_code, response.url) == (302, _detail_url(course))


@pytest.mark.django_db
@time_machine.travel(datetime(2026, 9, 1, 10, 0, tzinfo=UTC), tick=False)
@pytest.mark.parametrize(
    "route", ["course_revision_start", "course_revision_answer", "course_revision_next"]
)
def test_post_routes_turn_away_an_ended_registration(route, mock_site_context):
    course = CourseFactory(time_limit_days=30)
    CourseDeadlineConfigFactory(course=course, end_course_access="on")
    user = UserFactory()
    course_progress_record(
        course, user, created_at=datetime(2026, 3, 1, 10, 0, tzinfo=UTC)
    )

    response = _client_for(user).post(_route_url(route, course))

    assert (response.status_code, response.url) == (302, _detail_url(course))


@pytest.mark.django_db
@pytest.mark.parametrize(
    "route", ["course_revision_start", "course_revision_answer", "course_revision_next"]
)
def test_post_routes_do_not_find_a_course_on_another_site(route, mock_site_context):
    course = CourseFactory(site=SiteFactory())

    response = _client_for(UserFactory()).post(_route_url(route, course))

    assert response.status_code == 404


@pytest.mark.django_db
def test_empty_submit_returns_422_and_writes_nothing(mock_site_context):
    course, _, (question,), client = _banked_session()

    response = _post_answer(client, course, question, [])

    assert (response.status_code, RevisionReview.objects.count()) == (422, 0)


@pytest.mark.django_db
def test_second_submit_for_an_answered_question_writes_nothing(mock_site_context):
    course, user, (question,), client = _banked_session()
    RevisionReviewFactory(
        user=user,
        question=question,
        course=course,
        reviewed_at=datetime(2026, 6, 1, tzinfo=UTC),
        was_correct=False,
    )

    _post_answer(client, course, question, [str(_right_option(question).id)])

    assert RevisionReview.objects.count() == 1


@pytest.mark.django_db
def test_answer_ignores_an_option_of_another_question(mock_site_context):
    course, _, (question,), client = _banked_session()
    stranger = choice_question()

    response = _post_answer(client, course, question, [str(_right_option(stranger).id)])

    assert (response.status_code, RevisionReview.objects.count()) == (422, 0)


@pytest.mark.django_db
def test_right_answer_is_marked_correct_and_saved(mock_site_context):
    course, _, (question,), client = _banked_session()

    response = _post_answer(client, course, question, [str(_right_option(question).id)])

    assert response.status_code == 200
    assert RevisionReview.objects.get().was_correct is True


@pytest.mark.django_db
def test_unanswered_current_question_renders_the_question(mock_site_context):
    course, _, (question,), client = _banked_session()

    response = client.get(_revision_url(course))

    assert f"question_{question.id}" in response.content.decode()


@pytest.mark.django_db
def test_current_question_with_a_review_renders_its_feedback(mock_site_context):
    course, user, (question,), client = _banked_session()
    RevisionReviewFactory(
        user=user,
        question=question,
        course=course,
        reviewed_at=datetime(2026, 6, 1, tzinfo=UTC),
    )

    response = client.get(_revision_url(course))

    assert 'data-testid="revision-feedback"' in response.content.decode()


@pytest.mark.django_db
def test_state_past_its_last_question_renders_the_end_line(mock_site_context):
    course, user, (question,), client = _banked_session()
    RevisionReviewFactory(
        user=user,
        question=question,
        course=course,
        reviewed_at=datetime(2026, 6, 1, tzinfo=UTC),
        was_correct=True,
    )
    _store_session(client, course, [question], index=1)

    response = client.get(_revision_url(course))

    assert "1 answered, 1 right." in response.content.decode()


@pytest.mark.django_db
def test_question_that_left_the_bank_is_skipped_for_the_next(mock_site_context):
    course, _, (first, second), client = _banked_session(question_count=2)
    first.options.all().delete()

    response = client.get(_revision_url(course))

    assert f"question_{second.id}" in response.content.decode()


@pytest.mark.django_db
def test_next_with_the_current_question_unanswered_leaves_the_index(mock_site_context):
    course, _, _, client = _banked_session(question_count=2)

    client.post(_route_url("course_revision_next", course), HTTP_HX_REQUEST="true")

    assert _stored_index(client, course) == 0


@pytest.mark.django_db
def test_next_after_an_answer_moves_to_the_next_question(mock_site_context):
    course, user, (first, _), client = _banked_session(question_count=2)
    RevisionReviewFactory(
        user=user,
        question=first,
        course=course,
        reviewed_at=datetime(2026, 6, 1, tzinfo=UTC),
    )

    client.post(_route_url("course_revision_next", course), HTTP_HX_REQUEST="true")

    assert _stored_index(client, course) == 1


@pytest.mark.django_db
def test_learner_with_nothing_ready_sees_all_caught_up_and_no_start_button(
    mock_site_context,
):
    course = CourseFactory()
    user = UserFactory()
    course_progress_record(course, user)

    response = _client_for(user).get(_revision_url(course))

    content = response.content.decode()
    assert "You're all caught up." in content
    assert _route_url("course_revision_start", course) not in content


@pytest.mark.django_db
def test_start_with_nothing_ready_stores_no_session(mock_site_context):
    course = CourseFactory()
    user = UserFactory()
    course_progress_record(course, user)
    client = _client_for(user)

    client.post(_route_url("course_revision_start", course))

    assert f"revision_session:{course.id}" not in client.session


@pytest.mark.django_db
def test_start_with_ready_questions_stores_a_session(mock_site_context):
    course = CourseFactory()
    topic, _ = place_topic(course)
    question_testing_topic(topic)
    user = UserFactory()
    finish_topic(course_progress_record(course, user), topic)
    client = _client_for(user)

    response = client.post(_route_url("course_revision_start", course))

    assert (
        response.status_code,
        f"revision_session:{course.id}" in client.session,
    ) == (303, True)
