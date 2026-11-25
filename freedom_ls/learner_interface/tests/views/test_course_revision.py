"""The revision page: who may open it, the dashboard, answering a session and the done card."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import lxml.html
import pytest
import time_machine

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.deadlines.factories import (
    CourseDeadlineConfigFactory,
    CoursePauseFactory,
)
from freedom_ls.form_engine.models import FormQuestion, QuestionOption
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
from freedom_ls.tests.retire import retire

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse

DASHBOARD_QUERIES = 60


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
def test_unregistered_learner_is_sent_to_the_course_detail_page(
    mock_site_context,
) -> None:
    course = CourseFactory()
    client = _client_for(UserFactory())

    response = client.get(_revision_url(course))

    assert response.status_code == 302
    assert response.url == _detail_url(course)


@pytest.mark.django_db
def test_paused_course_sends_the_learner_to_the_course_detail_page(
    mock_site_context,
) -> None:
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
) -> None:
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
def test_course_on_another_site_is_not_found(mock_site_context) -> None:
    course = CourseFactory(site=SiteFactory())
    client = _client_for(UserFactory())

    response = client.get(_revision_url(course))

    assert response.status_code == 404


def _route_url(route: str, course) -> str:
    return reverse(f"learner_interface:{route}", kwargs={"course_slug": course.slug})


def _store_session(
    client: Client, course, questions, *, index: int = 0, started_at=None
) -> None:
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


def _banked_session(
    *, question_count: int = 1
) -> tuple[Course, User, list[FormQuestion], Client]:
    """A learner who finished a topic with questions, logged in with a session over them."""
    course: Course = CourseFactory()
    topic, _ = place_topic(course)
    questions = [question_testing_topic(topic) for _ in range(question_count)]
    user: User = UserFactory()
    finish_topic(course_progress_record(course, user), topic)
    client = _client_for(user)
    _store_session(client, course, questions)
    return course, user, questions, client


def _post_answer(
    client: Client, course: Course, question: FormQuestion, option_ids: list[str]
) -> _MonkeyPatchedWSGIResponse:
    return client.post(
        _route_url("course_revision_answer", course),
        {f"question_{question.id}": option_ids},
        HTTP_HX_REQUEST="true",
    )


@pytest.mark.django_db
def test_answer_posted_without_htmx_is_recorded_and_redirects_to_the_revision_page(
    mock_site_context,
) -> None:
    """A form submitted natively before htmx loaded used to be sent as a GET and lost the answer."""
    course, user, questions, client = _banked_session()
    question = questions[0]

    response = client.post(
        _route_url("course_revision_answer", course),
        {f"question_{question.id}": [str(_right_option(question).id)]},
    )

    assert (response.status_code, response.url) == (303, _revision_url(course))
    assert RevisionReview.objects.filter(user=user, question=question).exists()


def _right_option(question: FormQuestion) -> QuestionOption:
    return question.options.get(correct=True)


def _wrong_option(question: FormQuestion) -> QuestionOption:
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
def test_post_routes_turn_away_an_unregistered_learner(
    route, mock_site_context
) -> None:
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
def test_post_routes_turn_away_a_paused_course(route, mock_site_context) -> None:
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
def test_post_routes_turn_away_an_ended_registration(route, mock_site_context) -> None:
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
def test_post_routes_do_not_find_a_course_on_another_site(
    route, mock_site_context
) -> None:
    course = CourseFactory(site=SiteFactory())

    response = _client_for(UserFactory()).post(_route_url(route, course))

    assert response.status_code == 404


@pytest.mark.django_db
def test_empty_submit_returns_422_and_writes_nothing(mock_site_context) -> None:
    course, _, (question,), client = _banked_session()

    response = _post_answer(client, course, question, [])

    assert (response.status_code, RevisionReview.objects.count()) == (422, 0)


@pytest.mark.django_db
def test_second_submit_for_an_answered_question_writes_nothing(
    mock_site_context,
) -> None:
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
def test_answer_ignores_an_option_of_another_question(mock_site_context) -> None:
    course, _, (question,), client = _banked_session()
    stranger = choice_question()

    response = _post_answer(client, course, question, [str(_right_option(stranger).id)])

    assert (response.status_code, RevisionReview.objects.count()) == (422, 0)


@pytest.mark.django_db
def test_right_answer_is_marked_correct_and_saved(mock_site_context) -> None:
    course, _, (question,), client = _banked_session()

    response = _post_answer(client, course, question, [str(_right_option(question).id)])

    assert response.status_code == 200
    assert RevisionReview.objects.get().was_correct is True


@pytest.mark.django_db
def test_unanswered_current_question_renders_the_question(mock_site_context) -> None:
    course, _, (question,), client = _banked_session()

    response = client.get(_revision_url(course))

    assert f"question_{question.id}" in response.content.decode()


@pytest.mark.django_db
def test_current_question_with_a_review_renders_its_feedback(mock_site_context) -> None:
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
def test_question_that_left_the_bank_is_skipped_for_the_next(mock_site_context) -> None:
    course, _, (first, second), client = _banked_session(question_count=2)
    first.options.all().delete()

    response = client.get(_revision_url(course))

    assert f"question_{second.id}" in response.content.decode()


@pytest.mark.django_db
def test_next_with_the_current_question_unanswered_leaves_the_index(
    mock_site_context,
) -> None:
    course, _, _, client = _banked_session(question_count=2)

    client.post(_route_url("course_revision_next", course), HTTP_HX_REQUEST="true")

    assert _stored_index(client, course) == 0


@pytest.mark.django_db
def test_next_after_an_answer_moves_to_the_next_question(mock_site_context) -> None:
    course, user, (first, _), client = _banked_session(question_count=2)
    RevisionReviewFactory(
        user=user,
        question=first,
        course=course,
        reviewed_at=datetime(2026, 6, 1, tzinfo=UTC),
    )

    client.post(_route_url("course_revision_next", course), HTTP_HX_REQUEST="true")

    assert _stored_index(client, course) == 1


def _course_with_everything_scheduled_later(
    *, due_in: timedelta
) -> tuple[Course, User, FormQuestion]:
    """A learner who finished a section whose only question is scheduled `due_in` from now."""
    course: Course = CourseFactory()
    topic, _ = place_topic(course)
    question = question_testing_topic(topic)
    user: User = UserFactory()
    finish_topic(course_progress_record(course, user), topic)
    RevisionScheduleFactory(
        user=user, question=question, due=datetime.now(UTC) + due_in
    )
    return course, user, question


@pytest.mark.django_db
def test_empty_bank_says_questions_appear_after_a_section_and_links_to_the_course(
    mock_site_context,
) -> None:
    course = CourseFactory()
    topic, _ = place_topic(course)
    question_testing_topic(topic)
    user = UserFactory()
    course_progress_record(course, user)

    response = _client_for(user).get(_revision_url(course))

    content = response.content.decode()
    home = reverse("learner_interface:course_home", kwargs={"course_slug": course.slug})
    assert response.status_code == 200
    assert "Questions appear here after you finish a section." in content
    assert f'href="{home}"' in content


@pytest.mark.django_db
def test_start_with_nothing_ready_stores_no_session(mock_site_context) -> None:
    course = CourseFactory()
    user = UserFactory()
    course_progress_record(course, user)
    client = _client_for(user)

    client.post(_route_url("course_revision_start", course))

    assert f"revision_session:{course.id}" not in client.session


@pytest.mark.django_db
def test_start_with_ready_questions_stores_a_session(mock_site_context) -> None:
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


def _option_texts_in_order(html: str, options) -> list[str]:
    """The option texts, in the order they appear in `html`."""
    return sorted((option.text for option in options), key=html.index)


@pytest.mark.django_db
def test_card_renders_options_in_the_order_the_stored_seed_gives(
    mock_site_context,
) -> None:
    course, _, (question,), client = _banked_session()
    expected = [o.text for o in shuffled_options(question, 1)]

    html = client.get(_revision_url(course)).content.decode()

    assert _option_texts_in_order(html, question.options.all()) == expected


@pytest.mark.django_db
def test_feedback_renders_options_in_the_order_the_stored_seed_gives(
    mock_site_context,
) -> None:
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
def test_start_stores_a_seed_from_new_seed(mock_site_context) -> None:
    course = CourseFactory()
    topic, _ = place_topic(course)
    question_testing_topic(topic)
    user = UserFactory()
    finish_topic(course_progress_record(course, user), topic)
    client = _client_for(user)

    with patch("freedom_ls.revision.services.new_seed", return_value=4242):
        client.post(_route_url("course_revision_start", course))

    assert client.session[f"revision_session:{course.id}"]["seeds"] == [4242]


def _course_with_due_backlog(user: User, size: int) -> Course:
    """A course whose learner has `size` reviewed questions due."""
    course: Course = CourseFactory()
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
def test_session_over_a_long_backlog_holds_the_configured_size(
    mock_site_context, settings
) -> None:
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
def test_feedback_shows_no_why_block_for_a_question_without_an_explanation(
    mock_site_context,
) -> None:
    html = _feedback_html(explanation="", answer_correctly=True)

    assert 'data-testid="revision-explanation"' not in html


def _answered_html(
    *, answer_correctly: bool
) -> tuple[Course, FormQuestion, QuestionOption, str]:
    course, _, (question,), client = _banked_session()
    option = _right_option(question) if answer_correctly else _wrong_option(question)
    _post_answer(client, course, question, [str(option.id)])
    html = client.get(_revision_url(course)).content.decode()
    return course, question, option, html


@pytest.mark.django_db
def test_wrong_answer_marks_the_chosen_option_and_the_correct_one(
    mock_site_context,
) -> None:
    _, _, _, html = _answered_html(answer_correctly=False)

    assert "Your answer" in html
    assert "Correct answer" in html


@pytest.mark.django_db
def test_right_answer_shows_no_wrong_choice_mark(mock_site_context) -> None:
    _, _, _, html = _answered_html(answer_correctly=True)

    assert "Your answer" not in html


@pytest.mark.django_db
def test_section_control_is_absent_when_the_placement_is_blocked(
    mock_site_context,
) -> None:
    course, _, (question,), client = _banked_session()
    option = _wrong_option(question)

    with patch(
        "freedom_ls.learner_interface.views._openable_positions", return_value={}
    ):
        _post_answer(client, course, question, [str(option.id)])
        html = client.get(_revision_url(course)).content.decode()

    assert "Revisit: " not in html


@pytest.mark.django_db
def test_feedback_root_is_announced_and_takes_focus(mock_site_context) -> None:
    _, _, _, html = _answered_html(answer_correctly=False)

    assert 'id="revision-feedback"' in html
    assert 'aria-live="polite"' in html
    assert 'tabindex="-1"' in html
    assert 'x-data="revisionFeedback"' in html


def _post_guessed(client: Client, course: Course) -> _MonkeyPatchedWSGIResponse:
    return client.post(
        _route_url("course_revision_guessed", course), HTTP_HX_REQUEST="true"
    )


def _right_answer_then_guessed() -> tuple[Course, FormQuestion, Client]:
    course, _, (question,), client = _banked_session()
    _post_answer(client, course, question, [str(_right_option(question).id)])
    return course, question, client


@pytest.mark.django_db
def test_guessed_post_after_a_right_answer_shows_the_toggle_pressed(
    mock_site_context,
) -> None:
    course, _, client = _right_answer_then_guessed()

    response = _post_guessed(client, course)

    assert (
        response.status_code,
        'aria-pressed="true"' in response.content.decode(),
        RevisionReview.objects.get().rating,
    ) == (200, True, 2)


@pytest.mark.django_db
def test_guessed_toggle_looks_different_when_pressed_than_when_released(
    mock_site_context,
) -> None:
    """A pressed toggle used to render exactly like a released one.

    Pressed is a filled button with a check icon, so it does not rely on colour alone.
    """
    course, _, client = _right_answer_then_guessed()

    def _toggle_markup(response) -> tuple[bool, bool]:
        html = response.content.decode()
        marker = html.index('data-testid="revision-guessed"')
        button = html[
            html.rindex("<button", 0, marker) : html.index("</button>", marker)
        ]
        return 'data-variant="primary"' in button, "<svg" in button

    pressed = _toggle_markup(_post_guessed(client, course))
    released = _toggle_markup(_post_guessed(client, course))

    assert (pressed, released) == ((True, True), (False, False))


@pytest.mark.django_db
def test_guessed_post_on_a_guessed_review_shows_the_toggle_released(
    mock_site_context,
) -> None:
    course, _, client = _right_answer_then_guessed()
    _post_guessed(client, course)

    response = _post_guessed(client, course)

    assert (
        'aria-pressed="false"' in response.content.decode(),
        RevisionReview.objects.get().rating,
    ) == (True, 3)


@pytest.mark.django_db
def test_guessed_post_with_the_question_unanswered_returns_422(
    mock_site_context,
) -> None:
    course, _, _, client = _banked_session()

    response = _post_guessed(client, course)

    assert response.status_code == 422


@pytest.mark.django_db
def test_guessed_post_after_the_session_moved_on_returns_422(mock_site_context) -> None:
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
def test_guessed_toggle_is_absent_after_a_wrong_answer(mock_site_context) -> None:
    _, _, _, html = _answered_html(answer_correctly=False)

    assert 'data-testid="revision-guessed"' not in html


@pytest.mark.django_db
def test_guessed_toggle_is_offered_after_a_right_answer(mock_site_context) -> None:
    _, _, _, html = _answered_html(answer_correctly=True)

    assert "We'll ask you this one again sooner." in html


def _ended_session(
    *, answer_correctly: bool
) -> tuple[Course, User, FormQuestion, Client]:
    """A session whose one question was answered and whose index is past the end."""
    course, user, (question,), client = _banked_session()
    option = _right_option(question) if answer_correctly else _wrong_option(question)
    _post_answer(client, course, question, [str(option.id)])
    _store_session(client, course, [question], index=1)
    return course, user, question, client


@pytest.mark.django_db
def test_dashboard_counts_the_due_questions_of_the_learners_bank(
    mock_site_context,
) -> None:
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

    content = response.content.decode()
    assert response.status_code == 200
    assert re.search(r"2 questions due\.", content) is not None
    assert "Start revision" in content


@pytest.mark.django_db
def test_dashboard_says_one_question_due_in_the_singular(mock_site_context) -> None:
    course, user, _, _ = _banked_session()

    content = _client_for(user).get(_revision_url(course)).content.decode()

    assert re.search(r"1 question due\.", content) is not None


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("backlog", "expected"), [(45, "40+ questions due."), (40, "40 questions due.")]
)
def test_dashboard_caps_a_long_backlog_at_forty_plus(
    backlog, expected, mock_site_context
) -> None:
    user = UserFactory()
    course = _course_with_due_backlog(user, backlog)

    content = _client_for(user).get(_revision_url(course)).content.decode()

    assert re.search(re.escape(expected), content) is not None


@pytest.mark.django_db
def test_dashboard_with_nothing_due_still_offers_to_start(mock_site_context) -> None:
    course, user, _ = _course_with_everything_scheduled_later(due_in=timedelta(days=3))

    content = _client_for(user).get(_revision_url(course)).content.decode()

    assert "Nothing is due." in content
    assert f'action="{_route_url("course_revision_start", course)}"' in content


@pytest.mark.django_db
def test_start_with_nothing_due_stores_a_session_of_bank_questions(
    mock_site_context,
) -> None:
    course, user, question = _course_with_everything_scheduled_later(
        due_in=timedelta(days=3)
    )
    client = _client_for(user)

    client.post(_route_url("course_revision_start", course))

    stored = client.session[f"revision_session:{course.id}"]
    assert stored["question_ids"] == [str(question.pk)]


@pytest.mark.django_db
def test_revision_page_renders_inside_the_course_player(mock_site_context) -> None:
    course, user, _, _ = _banked_session()
    topic_url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )

    content = _client_for(user).get(_revision_url(course)).content.decode()

    assert 'id="course-toc-region"' in content
    assert f'href="{topic_url}"' in content


@pytest.mark.django_db
def test_revision_page_marks_the_outline_entry_as_the_current_page(
    mock_site_context,
) -> None:
    course, user, _, _ = _banked_session()

    content = _client_for(user).get(_revision_url(course)).content.decode()

    entry = re.search(r'data-testid="revision-link".*?</nav>', content, re.S)
    assert entry is not None
    assert 'aria-current="page"' in entry.group(0)
    assert "1 due" in entry.group(0)


@pytest.mark.django_db
def test_revision_page_highlights_the_outline_entry_like_the_reference_link(
    mock_site_context,
) -> None:
    course, user, _, _ = _banked_session()

    content = _client_for(user).get(_revision_url(course)).content.decode()

    [link] = lxml.html.fromstring(content).cssselect(
        '[data-testid="revision-link"] a[aria-current="page"]'
    )
    classes = set(link.get("class", "").split())
    assert {"bg-primary/10", "rounded", "text-on-surface"} <= classes
    assert "bg-primary/5" not in classes


@pytest.mark.django_db
def test_revision_page_has_no_section_list_or_needs_revision_badge(
    mock_site_context,
) -> None:
    course, user, _, _ = _banked_session()

    content = _client_for(user).get(_revision_url(course)).content.decode()

    assert "All sections" not in content
    assert "Needs revision" not in content
    assert "ready" not in content


@pytest.mark.django_db
def test_check_answer_button_is_full_width(mock_site_context) -> None:
    course, _, _, client = _banked_session()

    content = client.get(_revision_url(course)).content.decode()

    button = re.search(r"<button[^>]*>(?:(?!</button>).)*Check answer", content, re.S)
    assert button is not None
    assert "w-full" in button.group(0)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("answer_correctly", "tone"), [(True, "success"), (False, "error")]
)
def test_feedback_puts_the_explanation_in_a_callout_of_the_results_tone(
    answer_correctly, tone, mock_site_context
) -> None:
    html = _feedback_html(
        explanation="Because **it is**.", answer_correctly=answer_correctly
    )

    callout = re.search(
        r'<div class="callout callout-(\w+)[^>]*data-testid="revision-result".*?'
        r"<strong>it is</strong>",
        html,
        re.S,
    )
    assert callout is not None
    assert callout.group(1) == tone


@pytest.mark.django_db
def test_feedback_has_no_why_heading(mock_site_context) -> None:
    html = _feedback_html(explanation="Because.", answer_correctly=False)

    assert re.search(r"<h\d[^>]*>\s*Why\s*</h\d>", html) is None


@pytest.mark.django_db
def test_wrong_answer_callout_names_the_correct_answer(mock_site_context) -> None:
    _, question, _, html = _answered_html(answer_correctly=False)

    assert f"Not quite. The answer is {_right_option(question).text}." in html


@pytest.mark.django_db
def test_right_answer_callout_says_correct(mock_site_context) -> None:
    _, _, _, html = _answered_html(answer_correctly=True)

    assert re.search(r"<strong[^>]*>\s*Correct\.\s*</strong>", html) is not None


def _option_row(html: str, option) -> str:
    row = re.search(
        rf"<li[^>]*>\s*<span[^>]*>{re.escape(option.text)}</span>.*?</li>", html, re.S
    )
    assert row is not None
    return row.group(0)


@pytest.mark.django_db
def test_correct_option_row_has_a_success_border_and_tint(mock_site_context) -> None:
    _, question, _, html = _answered_html(answer_correctly=False)

    row = _option_row(html, _right_option(question))

    assert "border-success" in row
    assert "bg-success/10" in row


@pytest.mark.django_db
def test_wrongly_chosen_option_row_has_an_error_border_and_tint(
    mock_site_context,
) -> None:
    _, _, chosen, html = _answered_html(answer_correctly=False)

    row = _option_row(html, chosen)

    assert "border-error" in row
    assert "bg-error/10" in row


@pytest.mark.django_db
def test_section_control_is_a_revisit_link_in_the_callout(mock_site_context) -> None:
    course, _, _, html = _answered_html(answer_correctly=False)
    href = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )

    callout = html[html.index('data-testid="revision-result"') :]
    link = re.search(rf'<a[^>]*href="{re.escape(href)}"[^>]*>.*?</a>', callout, re.S)
    assert link is not None
    assert 'data-variant="link"' in link.group(0)
    assert "Revisit: " in link.group(0)


def _done_html(outcomes: list[str]) -> tuple[str, Client, object]:
    """The done card of a session with one question per outcome: knew, hard or forgot."""
    course, _, questions, client = _banked_session(question_count=len(outcomes))
    for question, outcome in zip(questions, outcomes, strict=True):
        option = (
            _wrong_option(question) if outcome == "forgot" else _right_option(question)
        )
        _post_answer(client, course, question, [str(option.id)])
        if outcome == "hard":
            _post_guessed(client, course)
        response = client.post(
            _route_url("course_revision_next", course), HTTP_HX_REQUEST="true"
        )
    return response.content.decode(), client, course


def _count(html: str, testid: str) -> str:
    found = re.search(rf'data-testid="{testid}"[^>]*>\s*([^<]*?)\s*<', html)
    assert found is not None
    return found.group(1)


@pytest.mark.django_db
def test_done_card_counts_knew_hard_and_forgot(mock_site_context) -> None:
    html, _, _ = _done_html(["knew", "knew", "hard", "forgot"])

    assert "Revision done" in html
    assert _count(html, "revision-answered") == "You answered 4 questions."
    assert (
        _count(html, "revision-knew"),
        _count(html, "revision-hard"),
        _count(html, "revision-forgot"),
    ) == ("2", "1", "1")


@pytest.mark.django_db
def test_done_card_counts_are_plain_figures_without_border_or_fill(
    mock_site_context,
) -> None:
    """Each count on the done card used to sit in its own bordered, filled tile."""
    html, _, _ = _done_html(["knew", "hard", "forgot"])

    counts = re.search(
        r'<dl[^>]*data-testid="revision-counts"[^>]*>.*?</dl>', html, re.DOTALL
    )
    assert counts is not None
    classes = " ".join(re.findall(r'class="([^"]*)"', counts.group(0))).split()
    assert not [c for c in classes if c.startswith(("border", "bg-", "rounded"))]


@pytest.mark.django_db
def test_done_card_has_one_button_back_to_the_course(mock_site_context) -> None:
    html, _, course = _done_html(["forgot"])
    home = reverse("learner_interface:course_home", kwargs={"course_slug": course.slug})

    assert re.findall(r'<a[^>]*href="([^"]*)"', html) == [home]
    assert "Back to the course" in html
    assert "<button" not in html


@pytest.mark.django_db
def test_done_card_shows_no_missed_list_and_no_next_revision(mock_site_context) -> None:
    html, _, _ = _done_html(["forgot"])

    assert "Revisit: " not in html
    assert "Revise more" not in html
    assert "Next question" not in html


@pytest.mark.django_db
def test_revision_page_after_the_done_card_is_the_dashboard_again(
    mock_site_context,
) -> None:
    _, client, course = _done_html(["knew"])

    content = client.get(_revision_url(course)).content.decode()

    assert 'data-testid="revision-dashboard"' in content
    assert "Revision done" not in content


@pytest.mark.django_db
def test_state_past_its_last_question_renders_the_done_card(mock_site_context) -> None:
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

    assert "You answered 1 question." in response.content.decode()


@pytest.mark.django_db
def test_dashboard_queries_stay_within_a_fixed_bound(
    mock_site_context, django_assert_max_num_queries
) -> None:
    user = UserFactory()
    course = _course_with_due_backlog(user, 20)
    client = _client_for(user)

    with django_assert_max_num_queries(DASHBOARD_QUERIES):
        client.get(_revision_url(course))


@pytest.mark.django_db
@pytest.mark.parametrize(
    "route",
    ["course_revision_answer", "course_revision_next", "course_revision_guessed"],
)
def test_htmx_post_with_no_session_is_sent_to_the_revision_page_by_hx_redirect(
    route, mock_site_context
) -> None:
    course, _, _, client = _banked_session()
    session = client.session
    del session[f"revision_session:{course.id}"]
    session.save()

    response = client.post(_route_url(route, course), HTTP_HX_REQUEST="true")

    assert (response.status_code, response["HX-Redirect"]) == (
        204,
        _revision_url(course),
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "route",
    ["course_revision_answer", "course_revision_next", "course_revision_guessed"],
)
def test_htmx_post_from_an_unregistered_learner_is_sent_away_by_hx_redirect(
    route, mock_site_context
) -> None:
    course = CourseFactory()
    client = _client_for(UserFactory())

    response = client.post(_route_url(route, course), HTTP_HX_REQUEST="true")

    assert (response.status_code, response["HX-Redirect"]) == (
        204,
        _detail_url(course),
    )


@pytest.mark.django_db
def test_an_answer_given_in_another_course_does_not_count_as_answered_here(
    mock_site_context,
) -> None:
    course, user, (question,), client = _banked_session()
    RevisionReviewFactory(
        user=user,
        question=question,
        course=CourseFactory(),
        reviewed_at=datetime(2026, 6, 1, tzinfo=UTC),
    )

    content = client.get(_revision_url(course)).content.decode()

    assert 'data-testid="revision-feedback"' not in content


@pytest.mark.django_db
def test_revision_page_outline_links_reference_topics_and_carries_the_deadline(
    mock_site_context,
) -> None:
    course, user, _, _ = _banked_session()

    response = _client_for(user).get(_revision_url(course))

    assert response.context["reference_linked"] is True
    assert "next_deadline_card" in response.context


@pytest.mark.django_db
def test_counter_leaves_out_a_question_that_left_the_bank(mock_site_context) -> None:
    course, _, questions, client = _banked_session(question_count=3)
    questions[1].options.all().delete()
    _store_session(client, course, questions, index=2)

    content = client.get(_revision_url(course)).content.decode()

    assert "2 of 2" in content


@pytest.mark.django_db
@pytest.mark.parametrize("route", ["course_reference", "course_finish"])
def test_reference_and_finish_pages_keep_the_outline_revision_entry(
    route, mock_site_context
) -> None:
    course, user, _, _ = _banked_session()

    response = _client_for(user).get(_route_url(route, course))

    assert response.context["revision_due_text"] == "1 due"


@pytest.mark.django_db
def test_question_retired_during_a_session_is_skipped_for_the_next(
    mock_site_context: object,
) -> None:
    course, _, (first, second), client = _banked_session(question_count=2)
    retire(first)

    response = client.get(_revision_url(course))

    html = response.content.decode()
    assert (f"question_{first.id}" in html, f"question_{second.id}" in html) == (
        False,
        True,
    )


@pytest.mark.django_db
def test_card_leaves_out_a_retired_option(mock_site_context: object) -> None:
    course, _, (question,), client = _banked_session()
    gone = retire(_wrong_option(question))

    response = client.get(_revision_url(course))

    assert str(gone.id) not in response.content.decode()


@pytest.mark.django_db
def test_answer_naming_a_retired_option_returns_422_and_writes_nothing(
    mock_site_context: object,
) -> None:
    course, _, (question,), client = _banked_session()
    gone = retire(_wrong_option(question))

    response = _post_answer(client, course, question, [str(gone.id)])

    assert (response.status_code, RevisionReview.objects.count()) == (422, 0)
