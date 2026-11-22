"""The revision page: who may open it and what the start screen shows."""

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
from freedom_ls.revision.tests.helpers import question_testing_topic
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
