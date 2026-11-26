"""Every quiz route completes a sitting whose time has run out and sends the
learner to the results, which say that time ran out."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import cast
from urllib.parse import urlencode

import pytest
import time_machine

from django.http import HttpResponse, QueryDict
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.deadlines.factories import (
    CourseDeadlineConfigFactory,
    CoursePauseFactory,
)
from freedom_ls.form_engine.enums import CompletionReason
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import Form, FormProgress, FormStrategy
from freedom_ls.learner_interface.tests.helpers import (
    course_with_form,
    form_attempt,
    set_due_date,
)
from freedom_ls.learner_interface.views import _save_page_and_complete
from freedom_ls.learner_progress.models import CourseFormAttempt, CourseProgress
from freedom_ls.learner_progress.tests.helpers import course_progress_record

LIMIT_MINUTES = 30
REGISTERED_AT = datetime(2026, 3, 1, 10, 0, tzinfo=UTC)
STARTED_AT = datetime(2026, 3, 2, 10, 0, tzinfo=UTC)
IN_TIME = STARTED_AT + timedelta(minutes=LIMIT_MINUTES - 5)
LATE = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)

Scenario = Callable[[Course, Form, CourseProgress], None]


def _timed_quiz(
    *, limit: int | None = LIMIT_MINUTES, submit_on_exit: bool = True
) -> Form:
    """A one-question quiz with a quiz time limit."""
    form: Form = FormFactory(
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=70,
        time_limit_minutes=limit,
        submit_on_exit=submit_on_exit,
    )
    page = FormPageFactory(form=form, order=0)
    question = FormQuestionFactory(form_page=page, type="multiple_choice", order=0)
    QuestionOptionFactory(question=question, correct=True)
    QuestionOptionFactory(question=question, correct=False)
    return form


def _open_sitting(course: Course, user: User, form: Form) -> FormProgress:
    sitting = form_attempt(course, user, form)
    FormProgress.objects.filter(pk=sitting.pk).update(start_time=STARTED_AT)
    sitting.refresh_from_db()
    return sitting


def _kwargs(course: Course) -> dict[str, object]:
    return {"course_slug": course.slug, "index": 1}


def _results_url(course: Course) -> str:
    return reverse("learner_interface:course_form_complete", kwargs=_kwargs(course))


def _location(response: HttpResponse) -> str:
    return cast("str", response["Location"])


def _request(client: Client, course: Course, route: str) -> HttpResponse:
    kwargs = _kwargs(course)
    if route == "form_fill_page":
        kwargs = {**kwargs, "page_number": 1}
    url = reverse(f"learner_interface:{route}", kwargs=kwargs)
    response = client.post(url) if route == "form_submit_and_exit" else client.get(url)
    return cast("HttpResponse", response)


REDIRECTING_ROUTES = [
    "view_course_item",
    "form_start",
    "form_declaration",
    "form_fill_page",
    "form_submit_and_exit",
]


def _plain(course: Course, form: Form, record: CourseProgress) -> None:
    return None


def _paused(course: Course, form: Form, record: CourseProgress) -> None:
    CoursePauseFactory(course_progress=record, started_at=STARTED_AT)


def _closed(course: Course, form: Form, record: CourseProgress) -> None:
    set_due_date(course, form, due_date=date(2026, 3, 10))
    CourseDeadlineConfigFactory(course=course, close_items="on")


def _access_ended(course: Course, form: Form, record: CourseProgress) -> None:
    Course.objects.filter(pk=course.pk).update(time_limit_days=30)
    CourseDeadlineConfigFactory(course=course, end_course_access="on")


SCENARIOS: dict[str, tuple[Scenario, bool]] = {
    "plain": (_plain, True),
    "paused": (_paused, True),
    "closed": (_closed, True),
    "access_ended": (_access_ended, True),
    "save_on_exit": (_plain, False),
}


@pytest.fixture
def timed_course(
    mock_site_context: object, client: Client
) -> tuple[Course, Form, User, CourseProgress]:
    """A registered, logged-in learner's course whose only item is a timed quiz."""
    user: User = UserFactory()
    form = _timed_quiz()
    course = course_with_form(form)
    record = course_progress_record(course, user, created_at=REGISTERED_AT)
    client.force_login(user)
    return course, form, user, record


@pytest.mark.django_db
@pytest.mark.parametrize("route", REDIRECTING_ROUTES)
@time_machine.travel(LATE, tick=False)
def test_a_route_completes_an_expired_sitting_as_time_expired(
    timed_course: tuple[Course, Form, User, CourseProgress],
    client: Client,
    route: str,
) -> None:
    course, form, user, _record = timed_course
    sitting = _open_sitting(course, user, form)

    _request(client, course, route)

    sitting.refresh_from_db()
    assert sitting.completion_reason == CompletionReason.TIME_EXPIRED


@pytest.mark.django_db
@pytest.mark.parametrize("route", REDIRECTING_ROUTES)
@time_machine.travel(LATE, tick=False)
def test_a_route_redirects_an_expired_sitting_to_the_results(
    timed_course: tuple[Course, Form, User, CourseProgress],
    client: Client,
    route: str,
) -> None:
    course, form, user, _record = timed_course
    _open_sitting(course, user, form)

    response = _request(client, course, route)

    assert _location(response) == _results_url(course)


@pytest.mark.django_db
@time_machine.travel(LATE, tick=False)
def test_the_results_route_completes_an_expired_sitting_as_time_expired(
    timed_course: tuple[Course, Form, User, CourseProgress], client: Client
) -> None:
    course, form, user, _record = timed_course
    sitting = _open_sitting(course, user, form)

    client.get(_results_url(course))

    sitting.refresh_from_db()
    assert sitting.completion_reason == CompletionReason.TIME_EXPIRED


@pytest.mark.django_db
@time_machine.travel(LATE, tick=False)
def test_the_results_route_renders_an_expired_sitting(
    timed_course: tuple[Course, Form, User, CourseProgress], client: Client
) -> None:
    course, form, user, _record = timed_course
    _open_sitting(course, user, form)

    response = client.get(_results_url(course))

    assert response.status_code == 200
    assert b"Time ran out" in response.content


@pytest.mark.django_db
@pytest.mark.parametrize("scenario", list(SCENARIOS))
@pytest.mark.parametrize("route", REDIRECTING_ROUTES)
@time_machine.travel(LATE, tick=False)
def test_an_expired_sitting_completes_whatever_gate_the_learner_is_behind(
    mock_site_context: object, client: Client, route: str, scenario: str
) -> None:
    mutate, submit_on_exit = SCENARIOS[scenario]
    user: User = UserFactory()
    form = _timed_quiz(submit_on_exit=submit_on_exit)
    course = course_with_form(form)
    record = course_progress_record(course, user, created_at=REGISTERED_AT)
    mutate(course, form, record)
    sitting = _open_sitting(course, user, form)
    client.force_login(user)

    response = _request(client, course, route)

    sitting.refresh_from_db()
    assert sitting.completion_reason == CompletionReason.TIME_EXPIRED
    assert _location(response) == _results_url(course)


@pytest.mark.django_db
@time_machine.travel(LATE, tick=False)
def test_form_start_creates_no_new_sitting_when_it_completes_an_expired_one(
    timed_course: tuple[Course, Form, User, CourseProgress], client: Client
) -> None:
    course, form, user, _record = timed_course
    _open_sitting(course, user, form)

    _request(client, course, "form_start")

    assert FormProgress.objects.count() == 1
    assert CourseFormAttempt.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("reason", "shown"),
    [
        (CompletionReason.TIME_EXPIRED, True),
        (CompletionReason.LEARNER_SUBMITTED, False),
    ],
)
def test_the_results_say_time_ran_out_only_for_a_time_expired_sitting(
    timed_course: tuple[Course, Form, User, CourseProgress],
    client: Client,
    reason: CompletionReason,
    shown: bool,
) -> None:
    course, form, user, _record = timed_course
    sitting = _open_sitting(course, user, form)
    with time_machine.travel(STARTED_AT + timedelta(minutes=1), tick=False):
        sitting.complete(reason)
    sitting.refresh_from_db()
    assert sitting.completion_reason == reason

    response = client.get(_results_url(course))

    assert (b"Time ran out" in response.content) is shown


@pytest.mark.django_db
@pytest.mark.parametrize("route", REDIRECTING_ROUTES)
@time_machine.travel(IN_TIME, tick=False)
def test_an_unexpired_sitting_is_left_open_by_every_route(
    timed_course: tuple[Course, Form, User, CourseProgress],
    client: Client,
    route: str,
) -> None:
    course, form, user, _record = timed_course
    sitting = _open_sitting(course, user, form)

    _request(client, course, route)

    sitting.refresh_from_db()
    assert sitting.completion_reason != CompletionReason.TIME_EXPIRED


@pytest.mark.django_db
@pytest.mark.parametrize("route", REDIRECTING_ROUTES)
@time_machine.travel(LATE, tick=False)
def test_an_untimed_quiz_is_never_expired_by_a_route(
    mock_site_context: object, client: Client, route: str
) -> None:
    user: User = UserFactory()
    form = _timed_quiz(limit=None)
    course = course_with_form(form)
    course_progress_record(course, user, created_at=REGISTERED_AT)
    sitting = _open_sitting(course, user, form)
    client.force_login(user)

    _request(client, course, route)

    sitting.refresh_from_db()
    assert sitting.completion_reason != CompletionReason.TIME_EXPIRED


@pytest.mark.django_db
@time_machine.travel(IN_TIME, tick=False)
def test_a_limit_shortened_on_the_form_expires_an_open_sitting_on_its_next_request(
    timed_course: tuple[Course, Form, User, CourseProgress], client: Client
) -> None:
    course, form, user, _record = timed_course
    sitting = _open_sitting(course, user, form)
    Form.objects.filter(pk=form.pk).update(time_limit_minutes=5)

    response = _request(client, course, "form_start")

    sitting.refresh_from_db()
    assert sitting.completion_reason == CompletionReason.TIME_EXPIRED
    assert _location(response) == _results_url(course)


@pytest.mark.django_db
@time_machine.travel(LATE, tick=False)
def test_a_limit_removed_from_the_form_leaves_an_open_sitting_open(
    timed_course: tuple[Course, Form, User, CourseProgress], client: Client
) -> None:
    course, form, user, _record = timed_course
    sitting = _open_sitting(course, user, form)
    Form.objects.filter(pk=form.pk).update(time_limit_minutes=None)

    _request(client, course, "form_fill_page")

    sitting.refresh_from_db()
    assert sitting.completed_time is None


@pytest.mark.django_db
@time_machine.travel(LATE, tick=False)
def test_a_learner_returning_late_gets_the_expiry_instant_as_the_completed_time(
    timed_course: tuple[Course, Form, User, CourseProgress], client: Client
) -> None:
    course, form, user, _record = timed_course
    sitting = _open_sitting(course, user, form)

    _request(client, course, "form_start")

    sitting.refresh_from_db()
    assert sitting.completed_time == STARTED_AT + timedelta(minutes=LIMIT_MINUTES)


@pytest.mark.django_db
@time_machine.travel(LATE, tick=False)
def test_a_learner_with_no_course_progress_record_is_not_given_one(
    mock_site_context: object, client: Client
) -> None:
    form = _timed_quiz()
    course = course_with_form(form)
    client.force_login(UserFactory())

    _request(client, course, "form_start")

    assert not CourseProgress.objects.exists()


EXPIRY = STARTED_AT + timedelta(minutes=LIMIT_MINUTES)

QuestionIds = dict[str, str]
PagedCourse = tuple[Course, Form, dict[int, QuestionIds], User, CourseProgress]


def _paged_quiz(
    *, limit: int | None = LIMIT_MINUTES, submit_on_exit: bool = True
) -> tuple[Form, dict[int, QuestionIds]]:
    """A two-page quiz; each page holds a required text question, an optional
    one and an email question, so a post can leave one blank or get one wrong."""
    form: Form = FormFactory(
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=70,
        time_limit_minutes=limit,
        submit_on_exit=submit_on_exit,
    )
    questions: dict[int, QuestionIds] = {}
    for number in (1, 2):
        page = FormPageFactory(form=form, order=number - 1)
        questions[number] = {
            "required": str(
                FormQuestionFactory(
                    form_page=page, type="short_text", order=0, required=True
                ).pk
            ),
            "optional": str(
                FormQuestionFactory(
                    form_page=page, type="short_text", order=1, required=False
                ).pk
            ),
            "email": str(
                FormQuestionFactory(
                    form_page=page, type="email", order=2, required=False
                ).pk
            ),
        }
    return form, questions


def _post_data(ids: QuestionIds, case: str) -> dict[str, str]:
    """What a page posts: the optional answer is always valid, so it is what a
    test looks for; `case` leaves the required one blank or gets the email wrong."""
    data = {f"question_{ids['optional']}": "kept"}
    if case != "required_unanswered":
        data[f"question_{ids['required']}"] = "also kept"
    if case == "invalid":
        data[f"question_{ids['email']}"] = "not an email"
    return data


def _time_up_data(ids: QuestionIds, case: str) -> dict[str, str]:
    return {**_post_data(ids, case), "time_up": "1", "page_number": "1"}


def _saved_answers(sitting: FormProgress) -> dict[str, str]:
    return {str(a.question_id): a.text_answer for a in sitting.answers.all()}


def _fill_url(course: Course, page_number: int) -> str:
    return reverse(
        "learner_interface:form_fill_page",
        kwargs={**_kwargs(course), "page_number": page_number},
    )


def _exit_url(course: Course) -> str:
    return reverse("learner_interface:form_submit_and_exit", kwargs=_kwargs(course))


@pytest.fixture
def paged_course(mock_site_context: object, client: Client) -> PagedCourse:
    user: User = UserFactory()
    form, questions = _paged_quiz()
    course = course_with_form(form)
    record = course_progress_record(course, user, created_at=REGISTERED_AT)
    client.force_login(user)
    return course, form, questions, user, record


CASES = ["valid", "required_unanswered", "invalid"]


@pytest.mark.django_db
@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("page_number", [1, 2])
def test_a_page_post_just_after_expiry_is_saved(
    paged_course: PagedCourse, client: Client, page_number: int, case: str
) -> None:
    course, form, questions, user, _record = paged_course
    sitting = _open_sitting(course, user, form)

    with time_machine.travel(EXPIRY + timedelta(seconds=8), tick=False):
        client.post(
            _fill_url(course, page_number), _post_data(questions[page_number], case)
        )

    assert _saved_answers(sitting)[questions[page_number]["optional"]] == "kept"


@pytest.mark.django_db
@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("page_number", [1, 2])
def test_a_page_post_just_after_expiry_completes_the_sitting_as_time_expired(
    paged_course: PagedCourse, client: Client, page_number: int, case: str
) -> None:
    course, form, questions, user, _record = paged_course
    sitting = _open_sitting(course, user, form)

    with time_machine.travel(EXPIRY + timedelta(seconds=8), tick=False):
        response = client.post(
            _fill_url(course, page_number), _post_data(questions[page_number], case)
        )

    sitting.refresh_from_db()
    assert sitting.completion_reason == CompletionReason.TIME_EXPIRED
    assert _location(response) == _results_url(course)


@pytest.mark.django_db
def test_a_page_post_after_the_grace_window_saves_nothing(
    paged_course: PagedCourse, client: Client
) -> None:
    course, form, questions, user, _record = paged_course
    sitting = _open_sitting(course, user, form)

    with time_machine.travel(EXPIRY + timedelta(seconds=11), tick=False):
        client.post(_fill_url(course, 1), _post_data(questions[1], "valid"))

    assert _saved_answers(sitting) == {}


@pytest.mark.django_db
def test_a_page_post_after_the_grace_window_still_lands_on_the_results(
    paged_course: PagedCourse, client: Client
) -> None:
    course, form, questions, user, _record = paged_course
    sitting = _open_sitting(course, user, form)

    with time_machine.travel(EXPIRY + timedelta(seconds=11), tick=False):
        response = client.post(_fill_url(course, 1), _post_data(questions[1], "valid"))

    sitting.refresh_from_db()
    assert sitting.completion_reason == CompletionReason.TIME_EXPIRED
    assert _location(response) == _results_url(course)


@pytest.mark.django_db
@pytest.mark.parametrize("scenario", ["paused", "closed", "access_ended"])
def test_a_page_post_inside_the_window_is_saved_whatever_gate_the_learner_is_behind(
    paged_course: PagedCourse, client: Client, scenario: str
) -> None:
    course, form, questions, user, record = paged_course
    SCENARIOS[scenario][0](course, form, record)
    sitting = _open_sitting(course, user, form)

    with time_machine.travel(EXPIRY + timedelta(seconds=5), tick=False):
        client.post(_fill_url(course, 1), _post_data(questions[1], "valid"))

    assert _saved_answers(sitting)[questions[1]["optional"]] == "kept"


@pytest.mark.django_db
def test_a_page_post_with_no_open_sitting_writes_nothing(
    paged_course: PagedCourse, client: Client
) -> None:
    course, _form, questions, _user, _record = paged_course

    with time_machine.travel(EXPIRY + timedelta(seconds=5), tick=False):
        client.post(_fill_url(course, 1), _post_data(questions[1], "valid"))

    assert FormProgress.objects.count() == 0


@pytest.mark.django_db
def test_a_page_post_never_changes_another_learners_sitting(
    paged_course: PagedCourse, client: Client
) -> None:
    course, form, questions, _user, _record = paged_course
    other: User = UserFactory()
    course_progress_record(course, other, created_at=REGISTERED_AT)
    others_sitting = _open_sitting(course, other, form)

    with time_machine.travel(EXPIRY + timedelta(seconds=5), tick=False):
        client.post(_fill_url(course, 1), _post_data(questions[1], "valid"))

    others_sitting.refresh_from_db()
    assert others_sitting.completed_time is None
    assert _saved_answers(others_sitting) == {}


@pytest.mark.django_db
@pytest.mark.parametrize("submit_on_exit", [True, False])
@pytest.mark.parametrize("case", ["required_unanswered", "invalid"])
@pytest.mark.parametrize("offset", [-5, 0, 10])
def test_a_time_up_post_inside_its_window_saves_the_page_and_completes(
    mock_site_context: object,
    client: Client,
    offset: int,
    case: str,
    submit_on_exit: bool,
) -> None:
    user: User = UserFactory()
    form, questions = _paged_quiz(submit_on_exit=submit_on_exit)
    course = course_with_form(form)
    course_progress_record(course, user, created_at=REGISTERED_AT)
    sitting = _open_sitting(course, user, form)
    client.force_login(user)

    with time_machine.travel(EXPIRY + timedelta(seconds=offset), tick=False):
        response = client.post(_exit_url(course), _time_up_data(questions[1], case))

    sitting.refresh_from_db()
    assert sitting.completion_reason == CompletionReason.TIME_EXPIRED
    assert _saved_answers(sitting)[questions[1]["optional"]] == "kept"
    assert _location(response) == _results_url(course)


@pytest.mark.django_db
def test_a_time_up_post_records_the_expiry_as_the_completed_time(
    paged_course: PagedCourse, client: Client
) -> None:
    course, form, questions, user, _record = paged_course
    sitting = _open_sitting(course, user, form)

    with time_machine.travel(EXPIRY + timedelta(seconds=8), tick=False):
        client.post(_exit_url(course), _time_up_data(questions[1], "valid"))

    sitting.refresh_from_db()
    assert sitting.completed_time == EXPIRY


@pytest.mark.django_db
def test_a_time_up_post_with_more_than_the_lead_left_saves_nothing(
    paged_course: PagedCourse, client: Client
) -> None:
    course, form, questions, user, _record = paged_course
    sitting = _open_sitting(course, user, form)

    with time_machine.travel(EXPIRY - timedelta(seconds=6), tick=False):
        client.post(_exit_url(course), _time_up_data(questions[1], "valid"))

    assert _saved_answers(sitting) == {}


@pytest.mark.django_db
def test_a_time_up_post_with_more_than_the_lead_left_completes_nothing(
    paged_course: PagedCourse, client: Client
) -> None:
    course, form, questions, user, _record = paged_course
    sitting = _open_sitting(course, user, form)

    with time_machine.travel(EXPIRY - timedelta(seconds=6), tick=False):
        client.post(_exit_url(course), _time_up_data(questions[1], "valid"))

    sitting.refresh_from_db()
    assert sitting.completed_time is None


@pytest.mark.django_db
def test_a_time_up_post_with_more_than_the_lead_left_returns_to_the_runner_page(
    paged_course: PagedCourse, client: Client
) -> None:
    course, form, questions, user, _record = paged_course
    _open_sitting(course, user, form)

    with time_machine.travel(EXPIRY - timedelta(seconds=6), tick=False):
        response = client.post(_exit_url(course), _time_up_data(questions[1], "valid"))

    assert _location(response) == _fill_url(course, 1)


@pytest.mark.django_db
def test_a_time_up_post_after_the_grace_window_saves_nothing(
    paged_course: PagedCourse, client: Client
) -> None:
    course, form, questions, user, _record = paged_course
    sitting = _open_sitting(course, user, form)

    with time_machine.travel(EXPIRY + timedelta(seconds=11), tick=False):
        client.post(_exit_url(course), _time_up_data(questions[1], "valid"))

    assert _saved_answers(sitting) == {}


@pytest.mark.django_db
def test_a_time_up_post_after_the_grace_window_still_completes_the_sitting(
    paged_course: PagedCourse, client: Client
) -> None:
    course, form, questions, user, _record = paged_course
    sitting = _open_sitting(course, user, form)

    with time_machine.travel(EXPIRY + timedelta(seconds=11), tick=False):
        response = client.post(_exit_url(course), _time_up_data(questions[1], "valid"))

    sitting.refresh_from_db()
    assert sitting.completion_reason == CompletionReason.TIME_EXPIRED
    assert _location(response) == _results_url(course)


@pytest.mark.django_db
def test_a_time_up_post_on_an_untimed_sitting_is_a_plain_exit(
    mock_site_context: object, client: Client
) -> None:
    user: User = UserFactory()
    form, questions = _paged_quiz(limit=None)
    course = course_with_form(form)
    course_progress_record(course, user, created_at=REGISTERED_AT)
    sitting = _open_sitting(course, user, form)
    client.force_login(user)

    with time_machine.travel(LATE, tick=False):
        client.post(_exit_url(course), _time_up_data(questions[1], "valid"))

    sitting.refresh_from_db()
    assert sitting.completion_reason == CompletionReason.LEARNER_SUBMITTED


@pytest.mark.django_db
def test_a_time_up_post_for_a_sitting_already_completed_saves_nothing(
    paged_course: PagedCourse, client: Client
) -> None:
    course, form, questions, user, _record = paged_course
    sitting = _open_sitting(course, user, form)
    with time_machine.travel(EXPIRY - timedelta(minutes=1), tick=False):
        sitting.complete()

    with time_machine.travel(EXPIRY + timedelta(seconds=1), tick=False):
        client.post(_exit_url(course), _time_up_data(questions[1], "valid"))

    assert _saved_answers(sitting) == {}


@pytest.mark.django_db
def test_saving_into_a_sitting_another_request_completed_changes_nothing(
    paged_course: PagedCourse,
) -> None:
    course, form, questions, user, record = paged_course
    stale = _open_sitting(course, user, form)
    with time_machine.travel(EXPIRY - timedelta(minutes=1), tick=False):
        FormProgress.objects.get(pk=stale.pk).complete()

    saved = _save_page_and_complete(
        record,
        stale,
        1,
        QueryDict(urlencode(_post_data(questions[1], "valid"))),
        EXPIRY + timedelta(seconds=1),
        FormProgress.accepts_time_up,
    )

    assert saved is False
    assert _saved_answers(stale) == {}


def _runner_page(client: Client, course: Course) -> HttpResponse:
    return cast("HttpResponse", client.get(_fill_url(course, 1)))


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("elapsed", "remaining_seconds", "remaining_text"),
    [
        (timedelta(0), 1800, "30:00"),
        (timedelta(minutes=29, seconds=59, milliseconds=400), 0, "0:00"),
        (timedelta(minutes=25, seconds=30, milliseconds=500), 269, "4:29"),
        (timedelta(minutes=29, seconds=5), 55, "0:55"),
    ],
)
def test_the_runner_context_counts_the_whole_seconds_left(
    paged_course: PagedCourse,
    client: Client,
    elapsed: timedelta,
    remaining_seconds: int,
    remaining_text: str,
) -> None:
    course, form, _, user, _ = paged_course
    _open_sitting(course, user, form)

    with time_machine.travel(STARTED_AT + elapsed, tick=False):
        response = _runner_page(client, course)

    assert response.context["remaining_seconds"] == remaining_seconds
    assert response.context["remaining_text"] == remaining_text


@pytest.mark.django_db
def test_the_runner_context_shows_hours_for_a_limit_of_an_hour_or_more(
    paged_course: PagedCourse, client: Client
) -> None:
    course, form, _, user, _ = paged_course
    Form.objects.filter(pk=form.pk).update(time_limit_minutes=125)
    _open_sitting(course, user, form)

    with time_machine.travel(STARTED_AT, tick=False):
        response = _runner_page(client, course)

    assert response.context["remaining_text"] == "2:05:00"


@pytest.mark.django_db
def test_an_untimed_runner_context_has_no_remaining_time(
    mock_site_context: object, client: Client
) -> None:
    user: User = UserFactory()
    form, _ = _paged_quiz(limit=None)
    course = course_with_form(form)
    course_progress_record(course, user, created_at=REGISTERED_AT)
    client.force_login(user)
    _open_sitting(course, user, form)

    with time_machine.travel(STARTED_AT, tick=False):
        response = _runner_page(client, course)

    assert response.context["remaining_seconds"] is None


@pytest.mark.django_db
def test_a_timed_runner_page_has_a_timer_named_time_left(
    paged_course: PagedCourse, client: Client
) -> None:
    course, form, _, user, _ = paged_course
    _open_sitting(course, user, form)

    with time_machine.travel(STARTED_AT, tick=False):
        html = _runner_page(client, course).content.decode()

    assert 'role="timer"' in html
    assert 'aria-label="Time left"' in html


@pytest.mark.django_db
def test_a_timed_runner_page_carries_the_countdown_data_attributes(
    paged_course: PagedCourse, client: Client
) -> None:
    course, form, _, user, _ = paged_course
    _open_sitting(course, user, form)

    with time_machine.travel(STARTED_AT, tick=False):
        html = _runner_page(client, course).content.decode()

    assert 'x-data="examCountdown"' in html
    assert 'data-remaining-seconds="1800"' in html
    assert f'data-time-up-url="{_exit_url(course)}"' in html


@pytest.mark.django_db
def test_an_untimed_runner_page_has_no_timer(
    mock_site_context: object, client: Client
) -> None:
    user: User = UserFactory()
    form, _ = _paged_quiz(limit=None)
    course = course_with_form(form)
    course_progress_record(course, user, created_at=REGISTERED_AT)
    client.force_login(user)
    _open_sitting(course, user, form)

    html = _runner_page(client, course).content.decode()

    assert 'role="timer"' not in html
    assert "data-remaining-seconds" not in html
