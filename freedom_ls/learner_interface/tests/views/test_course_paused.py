"""The player and course detail page for a learner whose course is paused."""

from __future__ import annotations

import datetime

import pytest
import time_machine

from django.test import Client
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.deadlines.actions import resume_course
from freedom_ls.deadlines.factories import CoursePauseFactory
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
)
from freedom_ls.form_engine.models import FormStrategy
from freedom_ls.learner_interface.tests.helpers import (
    form_attempt,
    set_due_date,
    topic_completion,
)
from freedom_ls.learner_interface.utils import COMPLETE, PAUSED
from freedom_ls.learner_progress.tests.helpers import course_progress_record

COMPLETED_AT = datetime.datetime(2026, 3, 1, 10, 0, tzinfo=datetime.UTC)


def _paused_course() -> tuple:
    """A course of a topic then a pass-marked quiz, with no deadline policy."""
    course = CourseFactory()
    course.items.create(child=TopicFactory(), order=0)
    form = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=70)
    course.items.create(child=form, order=1)
    return course, form


def _paused_learner(course, **pause_fields) -> tuple:
    user = UserFactory()
    record = course_progress_record(course, user)
    CoursePauseFactory(course_progress=record, **pause_fields)
    client = Client()
    client.force_login(user)
    return user, record, client


def _detail_url(course) -> str:
    return reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )


def _urls(course) -> dict[str, str]:
    kwargs = {"course_slug": course.slug}
    return {
        "course_home": reverse("learner_interface:course_home", kwargs=kwargs),
        "view_course_item": reverse(
            "learner_interface:view_course_item", kwargs={**kwargs, "index": 1}
        ),
        "form_item": reverse(
            "learner_interface:view_course_item", kwargs={**kwargs, "index": 2}
        ),
        "form_start": reverse(
            "learner_interface:form_start", kwargs={**kwargs, "index": 2}
        ),
        "form_fill_page": reverse(
            "learner_interface:form_fill_page",
            kwargs={**kwargs, "index": 2, "page_number": 1},
        ),
        "course_finish": reverse("learner_interface:course_finish", kwargs=kwargs),
        "course_form_complete": reverse(
            "learner_interface:course_form_complete", kwargs={**kwargs, "index": 2}
        ),
        "form_submit_and_exit": reverse(
            "learner_interface:form_submit_and_exit", kwargs={**kwargs, "index": 2}
        ),
    }


def _complete_topic(course, user) -> None:
    topic_completion(
        course, user, course.viewable_items()[0], complete_time=COMPLETED_AT
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "route",
    [
        "course_home",
        "view_course_item",
        "form_start",
        "form_fill_page",
        "course_finish",
        "course_form_complete",
    ],
)
def test_a_paused_learner_is_sent_to_the_detail_page(mock_site_context, route):
    course, _form = _paused_course()
    _user, _record, client = _paused_learner(course)

    response = client.get(_urls(course)[route])

    assert response.status_code == 302
    assert response["Location"] == _detail_url(course)


@pytest.mark.django_db
@pytest.mark.parametrize("route", ["form_submit_and_exit", "course_finish"])
def test_a_paused_learner_posting_to_a_write_route_changes_nothing(
    mock_site_context, route
):
    course, form = _paused_course()
    user, record, client = _paused_learner(course)
    attempt = form_attempt(course, user, form)

    response = client.post(_urls(course)[route])

    attempt.refresh_from_db()
    record.refresh_from_db()
    assert response["Location"] == _detail_url(course)
    assert attempt.completed_time is None
    assert record.completed_time is None


@pytest.mark.django_db
def test_mark_complete_posted_to_an_unfinished_topic_writes_nothing_while_paused(
    mock_site_context,
):
    course, _form = _paused_course()
    _user, record, client = _paused_learner(course)

    response = client.post(_urls(course)["view_course_item"], {"mark_complete": ""})

    assert response["Location"] == _detail_url(course)
    assert not record.topic_progress.exists()


@pytest.mark.django_db
def test_mark_complete_posted_to_a_completed_topic_redirects_and_keeps_its_time(
    mock_site_context,
):
    course, _form = _paused_course()
    user, _record, client = _paused_learner(course)
    completion = topic_completion(
        course, user, course.viewable_items()[0], complete_time=COMPLETED_AT
    )

    response = client.post(_urls(course)["view_course_item"], {"mark_complete": ""})

    completion.refresh_from_db()
    assert response["Location"] == _detail_url(course)
    assert completion.complete_time == COMPLETED_AT


@pytest.mark.django_db
def test_an_open_attempt_keeps_its_answers_and_continues_after_resume(
    mock_site_context,
):
    course, form = _paused_course()
    page = FormPageFactory(form=form, order=0)
    FormQuestionFactory(form_page=page, type="short_text", order=0)
    user, record, client = _paused_learner(course)
    attempt = form_attempt(course, user, form)
    urls = _urls(course)

    client.post(urls["form_submit_and_exit"], {"page_number": "1"})
    client.get(urls["form_fill_page"])
    attempt.refresh_from_db()
    assert attempt.completed_time is None

    resume_course(record, actor=None, reason="Back")
    response = client.get(urls["form_fill_page"])

    assert response.status_code == 200


@pytest.mark.django_db
def test_a_completed_topic_opens_for_a_paused_learner_and_writes_nothing(
    mock_site_context,
):
    course, _form = _paused_course()
    user, record, client = _paused_learner(course)
    _complete_topic(course, user)

    response = client.get(_urls(course)["view_course_item"])

    record.refresh_from_db()
    assert response.status_code == 200
    assert record.last_accessed_item is None
    assert record.started_at is None
    assert response.context["next_url"] is None
    assert response.context["previous_url"] is None
    assert b'name="mark_complete"' not in response.content


@pytest.mark.django_db
def test_a_completed_form_start_page_offers_no_buttons_while_paused(
    mock_site_context,
):
    course, form = _paused_course()
    user, _record, client = _paused_learner(course)
    _complete_topic(course, user)
    form_attempt(course, user, form, completed_time=COMPLETED_AT)

    response = client.get(_urls(course)["form_item"])

    assert response.status_code == 200
    assert response.context["buttons"] == []


@pytest.mark.django_db
def test_a_completed_form_start_page_does_not_finalise_a_retake_in_progress_while_paused(
    mock_site_context,
):
    course, form = _paused_course()
    form.submit_on_exit = True
    form.save()
    user, _record, client = _paused_learner(course)
    _complete_topic(course, user)
    form_attempt(course, user, form, completed_time=COMPLETED_AT)
    retake = form_attempt(course, user, form)

    client.get(_urls(course)["form_item"])

    retake.refresh_from_db()
    assert retake.completed_time is None


@pytest.mark.django_db
def test_results_of_a_completed_attempt_open_without_retry_next_or_previous_while_paused(
    mock_site_context,
):
    course, form = _paused_course()
    user, _record, client = _paused_learner(course)
    form_attempt(
        course,
        user,
        form,
        completed_time=COMPLETED_AT,
        scores={"score": 1, "max_score": 2},
    )

    response = client.get(_urls(course)["course_form_complete"])

    html = response.content.decode()
    assert response.status_code == 200
    assert response.context["paused"] is True
    assert response.context["next_url"] is None
    assert response.context["previous_url"] is None
    assert f'href="{response.context["retry_url"]}"' not in html
    assert "try again" not in html


@pytest.mark.django_db
def test_the_outline_of_a_paused_learner_marks_unfinished_rows_paused_without_deadlines(
    mock_site_context,
):
    course, _form = _paused_course()
    user, _record, client = _paused_learner(course)
    _complete_topic(course, user)
    set_due_date(course, course.viewable_items()[1], due_date=datetime.date(2026, 5, 1))

    response = client.get(_detail_url(course))

    done, todo = response.context["children"]
    assert (done["status"], todo["status"]) == (COMPLETE, PAUSED)
    assert done["url"] is not None
    assert todo["url"] is None
    assert todo["due_at"] is None
    assert todo["deadline_tier"] is None
    assert b'data-testid="outline-row-paused"' in response.content


@pytest.mark.django_db
@pytest.mark.parametrize("planned", [True, False])
def test_the_detail_page_of_a_paused_learner_shows_the_callout_and_no_cta_or_reason(
    mock_site_context, planned
):
    course, _form = _paused_course()
    fields = {"planned_resume_on": datetime.date(2099, 1, 5)} if planned else {}
    _user, _record, client = _paused_learner(
        course, reason="private staff reason", **fields
    )

    response = client.get(_detail_url(course))

    html = response.content.decode()
    assert response.context["start_url"] is None
    assert response.context["cta_label"] is None
    assert response.context["paused_at"] is not None
    assert (response.context["planned_resume_at"] is not None) is planned
    assert 'data-testid="course-paused-callout"' in html
    assert "Your deadlines move by the time paused." in html
    assert "private staff reason" not in html


@pytest.mark.django_db
def test_once_the_planned_resume_passes_the_player_opens_again_and_writes_nothing(
    mock_site_context,
):
    course, _form = _paused_course()
    _user, record, client = _paused_learner(
        course, planned_resume_on=timezone.now().date() + datetime.timedelta(days=1)
    )

    with time_machine.travel(timezone.now() + datetime.timedelta(days=3), tick=False):
        response = client.get(_urls(course)["view_course_item"])

    assert response.status_code == 200
    assert response.context["paused"] is False
    assert record.pauses.get().ended_at is None
