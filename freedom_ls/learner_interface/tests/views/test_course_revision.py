"""The revision page: who may open it, the start screen and answering a session."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

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
from freedom_ls.revision.factories import (
    RevisionReviewFactory,
    RevisionScheduleFactory,
)
from freedom_ls.revision.models import RevisionReview
from freedom_ls.revision.services import RevisionSessionState, shuffled_options
from freedom_ls.revision.tests.helpers import (
    choice_question,
    finish_topic,
    place_topic,
    question_testing_topic,
)
from freedom_ls.tests.factories import SiteFactory

QUERIES_BASE = 42
QUERIES_PER_SECTION = 2


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
        seeds=tuple(range(1, len(questions) + 1)),
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
    "route",
    [
        "course_revision_start",
        "course_revision_answer",
        "course_revision_next",
        "course_revision_guessed",
    ],
)
def test_post_routes_turn_away_an_unregistered_learner(route, mock_site_context):
    course = CourseFactory()
    client = _client_for(UserFactory())

    response = client.post(_route_url(route, course))

    assert (response.status_code, response.url) == (302, _detail_url(course))


@pytest.mark.django_db
@pytest.mark.parametrize(
    "route",
    [
        "course_revision_start",
        "course_revision_answer",
        "course_revision_next",
        "course_revision_guessed",
    ],
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
    "route",
    [
        "course_revision_start",
        "course_revision_answer",
        "course_revision_next",
        "course_revision_guessed",
    ],
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
    "route",
    [
        "course_revision_start",
        "course_revision_answer",
        "course_revision_next",
        "course_revision_guessed",
    ],
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


def _start_section_url(course, section_id) -> str:
    return f"{_route_url('course_revision_start', course)}?section={section_id}"


def _two_finished_sections():
    course = CourseFactory()
    first, _ = place_topic(course, order=0)
    second, _ = place_topic(course, order=1)
    user = UserFactory()
    record = course_progress_record(course, user)
    finish_topic(record, first)
    finish_topic(record, second)
    return course, user, first, second


@pytest.mark.django_db
def test_start_screen_lists_only_sections_with_bank_questions(mock_site_context):
    course, user, first, second = _two_finished_sections()
    question_testing_topic(first)

    content = _client_for(user).get(_revision_url(course)).content.decode()

    assert (first.title in content, second.title in content) == (True, False)


@pytest.mark.django_db
def test_start_screen_lists_sections_in_course_order(mock_site_context):
    course, user, first, second = _two_finished_sections()
    question_testing_topic(first)
    question_testing_topic(second)

    content = _client_for(user).get(_revision_url(course)).content.decode()

    assert content.index(first.title) < content.index(second.title)


@pytest.mark.django_db
def test_section_start_stores_a_session_of_that_sections_questions_only(
    mock_site_context,
):
    course, user, first, second = _two_finished_sections()
    wanted = question_testing_topic(first)
    question_testing_topic(second)
    client = _client_for(user)

    client.post(_start_section_url(course, first.pk))

    stored = client.session[f"revision_session:{course.id}"]["question_ids"]
    assert stored == [str(wanted.pk)]


@pytest.mark.django_db
def test_section_ready_count_reads_ten_plus_past_the_cap(mock_site_context):
    course, user, first, _second = _two_finished_sections()
    for _ in range(11):
        question_testing_topic(first)

    response = _client_for(user).get(_revision_url(course))

    assert "10+ ready" in response.content.decode()


@pytest.mark.django_db
def test_section_start_with_an_unknown_id_is_not_found(mock_site_context):
    course, user, _first, _second = _two_finished_sections()

    response = _client_for(user).post(_start_section_url(course, uuid4()))

    assert response.status_code == 404


@pytest.mark.django_db
def test_section_start_with_a_section_of_another_course_is_not_found(
    mock_site_context,
):
    course, user, first, _second = _two_finished_sections()
    question_testing_topic(first)
    other_course = CourseFactory()
    foreign, _ = place_topic(other_course)
    question_testing_topic(foreign)
    finish_topic(course_progress_record(other_course, user), foreign)

    response = _client_for(user).post(_start_section_url(course, foreign.pk))

    assert response.status_code == 404


@pytest.mark.django_db
def test_section_with_nothing_ready_has_a_disabled_button(mock_site_context):
    course, user, first, _second = _two_finished_sections()
    question = question_testing_topic(first)
    RevisionScheduleFactory(
        user=user, question=question, due=datetime(2099, 1, 1, tzinfo=UTC)
    )

    content = _client_for(user).get(_revision_url(course)).content.decode()

    assert re.search(r"<button[^>]*disabled[^>]*>\s*Revise", content) is not None


def _finished_course_with_sections(section_count: int):
    course = CourseFactory()
    user = UserFactory()
    record = course_progress_record(course, user)
    for order in range(section_count):
        topic, _ = place_topic(course, order=order)
        question_testing_topic(topic)
        finish_topic(record, topic)
    return course, user


@pytest.mark.django_db
@pytest.mark.parametrize("section_count", [2, 6])
def test_start_screen_queries_grow_by_a_fixed_step_per_section(
    section_count, mock_site_context, django_assert_max_num_queries
):
    course, user = _finished_course_with_sections(section_count)
    client = _client_for(user)

    with django_assert_max_num_queries(
        QUERIES_BASE + QUERIES_PER_SECTION * section_count
    ):
        client.get(_revision_url(course))


def _option_texts_in_order(html: str, options) -> list[str]:
    """The option texts, in the order they appear in `html`."""
    return sorted((option.text for option in options), key=html.index)


@pytest.mark.django_db
def test_card_renders_options_in_the_order_the_stored_seed_gives(mock_site_context):
    course, _, (question,), client = _banked_session()
    expected = [o.text for o in shuffled_options(question, 1)]

    html = client.get(_revision_url(course)).content.decode()

    assert _option_texts_in_order(html, question.options.all()) == expected


@pytest.mark.django_db
def test_feedback_renders_options_in_the_order_the_stored_seed_gives(
    mock_site_context,
):
    course, user, (question,), client = _banked_session()
    RevisionReviewFactory(
        user=user,
        question=question,
        course=course,
        reviewed_at=datetime(2026, 6, 1, tzinfo=UTC),
    )
    expected = [o.text for o in shuffled_options(question, 1)]

    html = client.get(_revision_url(course)).content.decode()

    assert _option_texts_in_order(html, question.options.all()) == expected


@pytest.mark.django_db
def test_start_stores_a_seed_from_new_seed(mock_site_context):
    course = CourseFactory()
    topic, _ = place_topic(course)
    question_testing_topic(topic)
    user = UserFactory()
    finish_topic(course_progress_record(course, user), topic)
    client = _client_for(user)

    with patch("freedom_ls.revision.services.new_seed", return_value=4242):
        client.post(_route_url("course_revision_start", course))

    assert client.session[f"revision_session:{course.id}"]["seeds"] == [4242]


def _course_with_due_backlog(user, size: int):
    """A course whose learner has `size` reviewed questions due."""
    course = CourseFactory()
    topic, _ = place_topic(course)
    finish_topic(course_progress_record(course, user), topic)
    now = datetime.now(UTC)
    for _ in range(size):
        RevisionScheduleFactory(
            user=user,
            question=question_testing_topic(topic),
            due=now - timedelta(days=1),
        )
    return course


@pytest.mark.django_db
def test_start_screen_caps_a_long_backlog_at_forty_plus(mock_site_context):
    user = UserFactory()
    course = _course_with_due_backlog(user, 45)

    response = _client_for(user).get(_revision_url(course))

    assert "40+ ready" in response.content.decode()


@pytest.mark.django_db
def test_start_screen_shows_forty_exactly_without_a_plus(mock_site_context):
    user = UserFactory()
    course = _course_with_due_backlog(user, 40)

    response = _client_for(user).get(_revision_url(course))

    assert "40 ready" in response.content.decode()


@pytest.mark.django_db
def test_session_over_a_long_backlog_holds_the_configured_size(
    mock_site_context, settings
):
    settings.REVISION_SESSION_SIZE = 15
    user = UserFactory()
    course = _course_with_due_backlog(user, 100)
    client = _client_for(user)

    client.post(_route_url("course_revision_start", course))

    stored = client.session[f"revision_session:{course.id}"]
    assert len(stored["question_ids"]) == 15


def _feedback_html(*, explanation: str, answer_correctly: bool) -> str:
    course, _, (question,), client = _banked_session()
    question.explanation = explanation
    question.save()
    option = _right_option(question) if answer_correctly else _wrong_option(question)
    _post_answer(client, course, question, [str(option.id)])

    return str(client.get(_revision_url(course)).content.decode())


@pytest.mark.django_db
@pytest.mark.parametrize("answer_correctly", [True, False], ids=["right", "wrong"])
def test_feedback_shows_the_explanation_after_an_answer(
    answer_correctly, mock_site_context
):
    html = _feedback_html(
        explanation="Because **it is**.", answer_correctly=answer_correctly
    )

    assert "<strong>it is</strong>" in html
    assert "Why" in html


@pytest.mark.django_db
def test_feedback_shows_no_why_block_for_a_question_without_an_explanation(
    mock_site_context,
):
    html = _feedback_html(explanation="", answer_correctly=True)

    assert 'data-testid="revision-explanation"' not in html


def _answered_html(*, answer_correctly: bool):
    course, _, (question,), client = _banked_session()
    option = _right_option(question) if answer_correctly else _wrong_option(question)
    _post_answer(client, course, question, [str(option.id)])
    html = client.get(_revision_url(course)).content.decode()
    return course, question, option, html


@pytest.mark.django_db
def test_wrong_answer_marks_the_chosen_option_and_the_correct_one(mock_site_context):
    _, _, _, html = _answered_html(answer_correctly=False)

    assert "Your answer" in html
    assert "Correct answer" in html


@pytest.mark.django_db
def test_right_answer_shows_no_wrong_choice_mark(mock_site_context):
    _, _, _, html = _answered_html(answer_correctly=True)

    assert "Your answer" not in html


@pytest.mark.django_db
def test_section_control_after_a_wrong_answer_is_a_filled_button(mock_site_context):
    course, _, _, html = _answered_html(answer_correctly=False)
    href = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )

    assert f'href="{href}"' in html
    assert 'data-variant="primary"' in html
    assert "Revise: " in html


@pytest.mark.django_db
def test_section_control_after_a_right_answer_is_a_link_button(mock_site_context):
    course, _, _, html = _answered_html(answer_correctly=True)
    href = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )

    assert f'href="{href}"' in html
    assert 'data-variant="link"' in html


@pytest.mark.django_db
def test_section_control_is_absent_when_the_placement_is_blocked(mock_site_context):
    course, _, (question,), client = _banked_session()
    option = _wrong_option(question)

    with patch(
        "freedom_ls.learner_interface.views._openable_positions", return_value={}
    ):
        _post_answer(client, course, question, [str(option.id)])
        html = client.get(_revision_url(course)).content.decode()

    assert "Revise: " not in html


@pytest.mark.django_db
def test_feedback_root_is_announced_and_takes_focus(mock_site_context):
    _, _, _, html = _answered_html(answer_correctly=False)

    assert 'id="revision-feedback"' in html
    assert 'aria-live="polite"' in html
    assert 'tabindex="-1"' in html
    assert 'x-data="revisionFeedback"' in html


def _post_guessed(client: Client, course):
    return client.post(
        _route_url("course_revision_guessed", course), HTTP_HX_REQUEST="true"
    )


def _right_answer_then_guessed():
    course, _, (question,), client = _banked_session()
    _post_answer(client, course, question, [str(_right_option(question).id)])
    return course, question, client


@pytest.mark.django_db
def test_guessed_post_after_a_right_answer_shows_the_toggle_pressed(mock_site_context):
    course, _, client = _right_answer_then_guessed()

    response = _post_guessed(client, course)

    assert (
        response.status_code,
        'aria-pressed="true"' in response.content.decode(),
        RevisionReview.objects.get().rating,
    ) == (200, True, 2)


@pytest.mark.django_db
def test_guessed_post_on_a_guessed_review_shows_the_toggle_released(mock_site_context):
    course, _, client = _right_answer_then_guessed()
    _post_guessed(client, course)

    response = _post_guessed(client, course)

    assert (
        'aria-pressed="false"' in response.content.decode(),
        RevisionReview.objects.get().rating,
    ) == (True, 3)


@pytest.mark.django_db
def test_guessed_post_with_the_question_unanswered_returns_422(mock_site_context):
    course, _, _, client = _banked_session()

    response = _post_guessed(client, course)

    assert response.status_code == 422


@pytest.mark.django_db
def test_guessed_post_after_the_session_moved_on_returns_422(mock_site_context):
    course, user, questions, client = _banked_session(question_count=2)
    RevisionReviewFactory(
        user=user,
        question=questions[0],
        course=course,
        reviewed_at=datetime(2026, 6, 1, tzinfo=UTC),
    )
    _store_session(client, course, questions, index=1)

    response = _post_guessed(client, course)

    assert response.status_code == 422


@pytest.mark.django_db
def test_guessed_toggle_is_absent_after_a_wrong_answer(mock_site_context):
    _, _, _, html = _answered_html(answer_correctly=False)

    assert 'data-testid="revision-guessed"' not in html


@pytest.mark.django_db
def test_guessed_toggle_is_offered_after_a_right_answer(mock_site_context):
    _, _, _, html = _answered_html(answer_correctly=True)

    assert "We'll ask you this one again sooner." in html
