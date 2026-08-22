"""Tests for webhook events fired from the student_interface app."""

from unittest.mock import patch

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.student_progress.factories import CourseProgressFactory


# transaction=True so that on_commit hooks for webhook event delivery fire under test
@pytest.mark.django_db(transaction=True)
class TestCourseCompletedWebhookEvent:
    def test_completing_course_fires_webhook_event(
        self, mock_site_context: object
    ) -> None:
        """Finishing a course for the first time fires course.completed event."""
        user = UserFactory(password="testpass")
        course = CourseFactory(slug="test-course")
        CourseProgressFactory(user=user, course=course, completed_time=None)

        client = Client()
        client.force_login(user)

        with patch("freedom_ls.webhooks.events.fire_webhook_event") as mock_fire:
            url = reverse(
                "student_interface:course_finish",
                kwargs={"course_slug": "test-course"},
            )
            client.get(url)

        mock_fire.assert_called_once()
        call_args = mock_fire.call_args
        assert call_args[0][0] == "course.completed"
        payload = call_args[0][1]
        assert payload["user_id"] == user.pk
        assert payload["user_email"] == user.email
        assert payload["course_id"] == str(course.id)
        assert payload["course_title"] == course.title
        assert "completed_time" in payload

    def test_revisiting_finish_page_does_not_fire_webhook_again(
        self, mock_site_context: object
    ) -> None:
        """If the course is already completed, no webhook event is fired."""
        from django.utils import timezone

        user = UserFactory(password="testpass")
        course = CourseFactory(slug="test-course-2")
        CourseProgressFactory(user=user, course=course, completed_time=timezone.now())

        client = Client()
        client.force_login(user)

        with patch("freedom_ls.webhooks.events.fire_webhook_event") as mock_fire:
            url = reverse(
                "student_interface:course_finish",
                kwargs={"course_slug": "test-course-2"},
            )
            client.get(url)

        mock_fire.assert_not_called()
