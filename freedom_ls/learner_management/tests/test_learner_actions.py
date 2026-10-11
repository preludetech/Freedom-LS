from __future__ import annotations

import pytest

from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.learner_actions import (
    deactivate_learner,
    reactivate_learner,
    remove_from_cohort,
)
from freedom_ls.learner_management.models import (
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.organisations.factories import OrganisationFactory
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


def _member(is_active_cohort: bool = True):
    cohort = CohortFactory(is_active=is_active_cohort)
    learner = LearnerFactory(organisation=cohort.organisation)
    CohortMembershipFactory(cohort=cohort, learner=learner)
    return learner, cohort


@pytest.mark.django_db
class TestRemoveFromCohort:
    def test_deletes_the_membership(self, mock_site_context):
        learner, cohort = _member()

        removed = remove_from_cohort(learner, cohort)

        assert (
            removed,
            CohortMembership.objects.filter(learner=learner, cohort=cohort).exists(),
        ) == (True, False)

    def test_records_one_member_removed_event_without_a_move_id(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        learner, cohort = _member()

        with django_capture_on_commit_callbacks(execute=True):
            remove_from_cohort(learner, cohort)

        event = WebhookEvent._base_manager.get()
        assert event.event_type == "cohort.member_removed"
        assert event.payload == {
            "user_id": learner.user.pk,
            "user_email": learner.user.email,
            "organisation_id": str(learner.organisation_id),
            "learner_id": str(learner.pk),
            "cohort_id": str(cohort.pk),
            "cohort_name": cohort.name,
            "move_id": None,
        }

    def test_a_repeat_returns_false(self, mock_site_context):
        learner, cohort = _member()
        remove_from_cohort(learner, cohort)

        assert remove_from_cohort(learner, cohort) is False

    def test_a_repeat_records_nothing(
        self, mock_site_context, django_capture_on_commit_callbacks
    ):
        learner, cohort = _member()
        remove_from_cohort(learner, cohort)

        with django_capture_on_commit_callbacks(execute=True):
            remove_from_cohort(learner, cohort)

        assert WebhookEvent._base_manager.count() == 0

    def test_refuses_another_organisations_cohort_and_changes_nothing(
        self, mock_site_context
    ):
        learner, _ = _member()
        elsewhere = CohortFactory(organisation=OrganisationFactory())

        with pytest.raises(ValueError, match="another organisation"):
            remove_from_cohort(learner, elsewhere)

        assert CohortMembership.objects.filter(learner=learner).count() == 1

    def test_refuses_an_inactive_cohort_and_changes_nothing(self, mock_site_context):
        learner, cohort = _member(is_active_cohort=False)

        with pytest.raises(ValueError, match="inactive"):
            remove_from_cohort(learner, cohort)

        assert CohortMembership.objects.filter(learner=learner).count() == 1
