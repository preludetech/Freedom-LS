"""Finishing a course raises no notification: the learner is on the completion page."""

from __future__ import annotations

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.comms.models import Notification
from freedom_ls.content_engine.factories import CourseFactory

from .conftest import course_progress_record


@pytest.mark.django_db(transaction=True)
def test_completing_a_course_notifies_nothing(mock_site_context: object) -> None:
    user = UserFactory(password="testpass")
    course = CourseFactory(slug="notify-course")
    record = course_progress_record(course, user)
    client = Client()
    client.force_login(user)

    client.get(
        reverse("learner_interface:course_finish", kwargs={"course_slug": course.slug})
    )

    record.refresh_from_db()
    assert record.completed_time is not None
    assert not Notification._base_manager.filter(
        user=user, category="course.completed"
    ).exists()
