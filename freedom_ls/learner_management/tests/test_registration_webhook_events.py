"""Tests for webhook events fired from the learner_management app."""

from unittest.mock import patch

import pytest

from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.learner_progress.models import CourseProgress


# transaction=True so that on_commit hooks for webhook event delivery fire under test
@pytest.mark.django_db(transaction=True)
class TestCourseRegisteredWebhookEvent:
    def test_creating_registration_fires_webhook_event(
        self, mock_site_context: object
    ) -> None:
        """Creating a new LearnerCourseRegistration fires course.registered event."""
        with patch("freedom_ls.webhooks.events.fire_webhook_event") as mock_fire:
            registration = LearnerCourseRegistrationFactory()

        record = CourseProgress.objects.get(learner_registration=registration)
        mock_fire.assert_called_once_with(
            "course.registered",
            {
                "user_id": registration.learner.user_id,
                "user_email": registration.learner.user.email,
                "course_id": str(registration.collection_id),
                "course_title": registration.collection.title,
                "registered_at": registration.registered_at.isoformat(),
                "organisation_id": str(registration.learner.organisation_id),
                "course_progress_id": str(record.id),
            },
        )

    def test_saving_existing_registration_does_not_fire_webhook(
        self, mock_site_context: object
    ) -> None:
        """Saving an existing LearnerCourseRegistration does not fire the event again."""
        registration = LearnerCourseRegistrationFactory()

        with patch("freedom_ls.webhooks.events.fire_webhook_event") as mock_fire:
            registration.is_active = False
            registration.save()

        mock_fire.assert_not_called()
