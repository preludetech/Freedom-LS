"""Every quiz route completes a sitting whose time has run out and sends the
learner to the results, which say that time ran out."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import cast

import pytest
import time_machine

from django.http import HttpResponse
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
