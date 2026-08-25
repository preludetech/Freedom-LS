"""Tests for webhook events fired from the learner_interface app."""

from unittest.mock import patch

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory

from .conftest import course_progress_record


# transaction=True so that on_commit hooks for webhook event delivery fire under test
@pytest.mark.django_db(transaction=True)
class TestCourseCompletedWebhookEvent:
    def test_completing_course_fires_webhook_event(
        self, mock_site_context: object
    ) -> None:
        """Finishing a course for the first time fires course.completed event."""
        user = UserFactory(password="testpass")
        course = CourseFactory(slug="test-course")
        course_progress_record(course, user)

        client = Client()
        client.force_login(user)

        with patch("freedom_ls.webhooks.events.fire_webhook_event") as mock_fire:
            url = reverse(
                "learner_interface:course_finish",
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

    def test_completed_payload_names_the_organisation_and_the_record(
        self, mock_site_context: object
    ) -> None:
        """A consumer has to know which of a learner's records completed."""
        user = UserFactory(password="testpass")
        course = CourseFactory(slug="payload-course")
        record = course_progress_record(course, user)

        client = Client()
        client.force_login(user)

        with patch("freedom_ls.webhooks.events.fire_webhook_event") as mock_fire:
            client.get(
                reverse(
                    "learner_interface:course_finish",
                    kwargs={"course_slug": "payload-course"},
                )
            )

        payload = mock_fire.call_args[0][1]
        assert payload["organisation_id"] == str(record.learner.organisation_id)
        assert payload["course_progress_id"] == str(record.id)

    def test_revisiting_finish_page_does_not_fire_webhook_again(
        self, mock_site_context: object
    ) -> None:
        """If the course is already completed, no webhook event is fired."""
        from django.utils import timezone

        user = UserFactory(password="testpass")
        course = CourseFactory(slug="test-course-2")
        record = course_progress_record(course, user)
        record.completed_time = timezone.now()
        record.save(update_fields=["completed_time"])

        client = Client()
        client.force_login(user)

        with patch("freedom_ls.webhooks.events.fire_webhook_event") as mock_fire:
            url = reverse(
                "learner_interface:course_finish",
                kwargs={"course_slug": "test-course-2"},
            )
            client.get(url)

        mock_fire.assert_not_called()

    def test_no_webhook_while_an_item_is_outstanding(
        self, mock_site_context: object
    ) -> None:
        """A false completion cannot be taken back once integrators have heard it."""
        user = UserFactory(password="testpass")
        course = CourseFactory(slug="outstanding-course")
        topic = TopicFactory(title="Unread", slug="outstanding-topic", content="x")
        course.items.create(child=topic, order=0)
        course_progress_record(course, user)

        client = Client()
        client.force_login(user)

        with patch("freedom_ls.webhooks.events.fire_webhook_event") as mock_fire:
            client.get(
                reverse(
                    "learner_interface:course_finish",
                    kwargs={"course_slug": "outstanding-course"},
                )
            )

        mock_fire.assert_not_called()
