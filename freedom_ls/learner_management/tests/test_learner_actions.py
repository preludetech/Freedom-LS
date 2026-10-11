from __future__ import annotations

import pytest

from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.learner_actions import (
    deactivate_learner,
    reactivate_learner,
)
from freedom_ls.learner_management.models import (
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.webhooks.models import WebhookEvent


@pytest.mark.django_db
class TestDeactivateLearner:
    def test_sets_the_learner_inactive_and_returns_true(self, mock_site_context):
        learner = LearnerFactory(is_active=True)

        changed = deactivate_learner(learner)

        learner.refresh_from_db()
        assert (changed, learner.is_active) == (True, False)

    def test_records_one_learner_deactivated_event_with_the_payload(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        learner = LearnerFactory(is_active=True)

        with django_capture_on_commit_callbacks(execute=True):
            deactivate_learner(learner)

        event = WebhookEvent._base_manager.get()
        assert event.event_type == "learner.deactivated"
        assert event.site_id == learner.site_id
        assert event.payload == {
            "user_id": learner.user.pk,
            "user_email": learner.user.email,
            "organisation_id": str(learner.organisation_id),
            "learner_id": str(learner.pk),
        }

    def test_a_second_call_returns_false(self, mock_site_context):
        learner = LearnerFactory(is_active=False)

        assert deactivate_learner(learner) is False

    def test_a_second_call_records_nothing(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        learner = LearnerFactory(is_active=False)

        with django_capture_on_commit_callbacks(execute=True):
            deactivate_learner(learner)

        assert WebhookEvent._base_manager.count() == 0

    def test_leaves_registrations_and_memberships_in_place(self, mock_site_context):
        learner = LearnerFactory(is_active=True)
        CohortMembershipFactory(learner=learner)
        LearnerCourseRegistrationFactory(learner=learner)

        deactivate_learner(learner)

        assert (
            CohortMembership.objects.filter(learner=learner).count(),
            LearnerCourseRegistration.objects.filter(
                learner=learner, is_active=True
            ).count(),
        ) == (1, 1)

    def test_leaves_cohort_registrations_active(self, mock_site_context):
        learner = LearnerFactory(is_active=True)
        membership = CohortMembershipFactory(learner=learner)
        registration = CohortCourseRegistrationFactory(cohort=membership.cohort)

        deactivate_learner(learner)

        registration.refresh_from_db()
        assert registration.is_active is True


@pytest.mark.django_db
class TestReactivateLearner:
    def test_sets_the_learner_active_and_returns_true(self, mock_site_context):
        learner = LearnerFactory(is_active=False)

        changed = reactivate_learner(learner)

        assert (changed, Learner.objects.get(pk=learner.pk).is_active) == (True, True)

    def test_records_one_learner_reactivated_event(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        learner = LearnerFactory(is_active=False)

        with django_capture_on_commit_callbacks(execute=True):
            reactivate_learner(learner)

        event = WebhookEvent._base_manager.get()
        assert (event.event_type, event.payload["learner_id"]) == (
            "learner.reactivated",
            str(learner.pk),
        )

    def test_a_second_call_returns_false_and_records_nothing(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        learner = LearnerFactory(is_active=True)

        with django_capture_on_commit_callbacks(execute=True):
            changed = reactivate_learner(learner)

        assert (changed, WebhookEvent._base_manager.count()) == (False, 0)
