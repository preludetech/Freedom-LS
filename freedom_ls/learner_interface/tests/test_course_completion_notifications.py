"""Finishing a course raises a course.completed notification.

Modelled on test_course_completion_webhook_events.py: transaction=True so the
notification's on_commit(..., robust=True) write and fire_webhook_event's own
task enqueue both run under test, exactly as they do outside one.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.comms.models import Notification
from freedom_ls.content_engine.factories import CourseFactory

from .conftest import course_progress_record


@pytest.mark.django_db(transaction=True)
class TestCourseCompletedNotification:
    def test_completing_course_writes_one_notification(
        self, mock_site_context: object
    ) -> None:
        user = UserFactory(password="testpass")
        course = CourseFactory(slug="notify-course")
        record = course_progress_record(course, user)

        client = Client()
        client.force_login(user)

        client.get(
            reverse(
                "learner_interface:course_finish",
                kwargs={"course_slug": "notify-course"},
            )
        )

        notifications = Notification._base_manager.filter(
            user=user, category="course.completed"
        )
        assert notifications.count() == 1
        notification = notifications.get()
        assert notification.data == {"course_title": course.title}
        assert notification.site_id == record.site_id

    def test_revisiting_finish_page_writes_no_second_notification(
        self, mock_site_context: object
    ) -> None:
        user = UserFactory(password="testpass")
        course = CourseFactory(slug="notify-course-2")
        course_progress_record(course, user)

        client = Client()
        client.force_login(user)

        url = reverse(
            "learner_interface:course_finish",
            kwargs={"course_slug": "notify-course-2"},
        )
        client.get(url)
        client.get(url)

        assert (
            Notification._base_manager.filter(
                user=user, category="course.completed"
            ).count()
            == 1
        )

    def test_notification_is_raised_before_the_webhook_event(
        self, mock_site_context: object
    ) -> None:
        order: list[str] = []
        user = UserFactory(password="testpass")
        course = CourseFactory(slug="notify-order-course")
        course_progress_record(course, user)

        client = Client()
        client.force_login(user)

        with (
            patch(
                "freedom_ls.comms.notify.raise_notification",
                side_effect=lambda **kwargs: order.append("notification"),
            ),
            patch(
                "freedom_ls.webhooks.events.fire_webhook_event",
                side_effect=lambda *args: order.append("webhook"),
            ),
        ):
            client.get(
                reverse(
                    "learner_interface:course_finish",
                    kwargs={"course_slug": "notify-order-course"},
                )
            )

        assert order == ["notification", "webhook"]

    def test_a_notification_write_failure_leaves_the_response_200(
        self, mock_site_context: object
    ) -> None:
        user = UserFactory(password="testpass")
        course = CourseFactory(slug="notify-fail-course")
        course_progress_record(course, user)

        client = Client()
        client.force_login(user)

        with patch(
            "freedom_ls.comms.models.Notification.objects.create",
            side_effect=RuntimeError,
        ):
            response = client.get(
                reverse(
                    "learner_interface:course_finish",
                    kwargs={"course_slug": "notify-fail-course"},
                )
            )

        assert response.status_code == 200

    def test_a_webhook_failure_leaves_the_completed_notification_written(
        self, mock_site_context: object
    ) -> None:
        user = UserFactory(password="testpass")
        course = CourseFactory(slug="notify-webhook-fail-course")
        course_progress_record(course, user)

        client = Client()
        client.force_login(user)

        with (
            patch(
                "freedom_ls.webhooks.events.fire_webhook_event",
                side_effect=RuntimeError,
            ),
            pytest.raises(RuntimeError),
        ):
            client.get(
                reverse(
                    "learner_interface:course_finish",
                    kwargs={"course_slug": "notify-webhook-fail-course"},
                )
            )

        assert Notification._base_manager.filter(
            user=user, category="course.completed"
        ).exists()
