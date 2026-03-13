"""Tests for webhook events fired from the student_management app."""

from unittest.mock import patch

import pytest

from freedom_ls.student_management.factories import UserCourseRegistrationFactory


@pytest.mark.django_db(transaction=True)
class TestCourseRegisteredWebhookEvent:
    def test_creating_registration_fires_webhook_event(
        self, mock_site_context: object
    ) -> None:
        """Creating a new UserCourseRegistration fires course.registered event."""
        with patch("freedom_ls.webhooks.events.fire_webhook_event") as mock_fire:
            registration = UserCourseRegistrationFactory()

        mock_fire.assert_called_once_with(
            "course.registered",
            {
                "user_id": registration.user_id,
                "user_email": registration.user.email,
                "course_id": str(registration.collection_id),
                "course_title": registration.collection.title,
                "registered_at": registration.registered_at.isoformat(),
            },
        )

    def test_saving_existing_registration_does_not_fire_webhook(
        self, mock_site_context: object
    ) -> None:
        """Saving an existing UserCourseRegistration does not fire the event again."""
        registration = UserCourseRegistrationFactory()

        with patch("freedom_ls.webhooks.events.fire_webhook_event") as mock_fire:
            registration.is_active = False
            registration.save()

        mock_fire.assert_not_called()
