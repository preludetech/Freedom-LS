"""Records are minted from registrations, by the receivers in signals.py.

The receivers defer their work to `transaction.on_commit`, which a test's
rolled-back transaction never reaches, so every test that expects a record
drives them through `django_capture_on_commit_callbacks`.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from django.core import serializers

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    CohortCourseRegistration,
    CohortMembership,
    LearnerCourseRegistration,
)
from freedom_ls.learner_progress.models import CourseProgress


@pytest.mark.django_db
class TestRegistrationMintsARecord:
    def test_registering_a_learner_creates_one_record(
        self, mock_site_context, django_capture_on_commit_callbacks
    ) -> None:
        learner = LearnerFactory()
        course = CourseFactory()

        with django_capture_on_commit_callbacks(execute=True):
            registration = LearnerCourseRegistrationFactory(
                learner=learner, collection=course
            )

        records = CourseProgress.objects.filter(learner=learner, course=course)
        assert records.count() == 1
        assert records.get().learner_registration_id == registration.pk

    def test_registering_a_cohort_creates_one_record_per_active_member(
        self, mock_site_context, django_capture_on_commit_callbacks
    ) -> None:
        cohort = CohortFactory()
        course = CourseFactory()
        member = CohortMembershipFactory(cohort=cohort)
        CohortMembershipFactory(
            cohort=cohort,
            learner=LearnerFactory(organisation=cohort.organisation, is_active=False),
        )

        with django_capture_on_commit_callbacks(execute=True):
            registration = CohortCourseRegistrationFactory(
                cohort=cohort, collection=course
            )

        records = CourseProgress.objects.filter(cohort_registration=registration)
        assert [record.learner_id for record in records] == [member.learner_id]

    def test_adding_a_member_to_a_registered_cohort_creates_a_record(
        self, mock_site_context, django_capture_on_commit_callbacks
    ) -> None:
        cohort = CohortFactory()
        registration = CohortCourseRegistrationFactory(cohort=cohort)

        with django_capture_on_commit_callbacks(execute=True):
            membership = CohortMembershipFactory(cohort=cohort)

        assert CourseProgress.objects.filter(
            learner=membership.learner, cohort_registration=registration
        ).exists()

    def test_adding_a_member_to_an_inactive_registration_creates_nothing(
        self, mock_site_context, django_capture_on_commit_callbacks
    ) -> None:
        """A withdrawn cohort registration grants nothing to a new member."""
        cohort = CohortFactory()
        CohortCourseRegistrationFactory(cohort=cohort, is_active=False)

        with django_capture_on_commit_callbacks(execute=True):
            CohortMembershipFactory(cohort=cohort)

        assert not CourseProgress.objects.exists()


@pytest.mark.django_db
class TestReRegistrationChangesNothing:
    """Registering again is a no-op, so a returning learner keeps their work."""

    def test_saving_the_registration_again_creates_no_second_record(
        self, mock_site_context, django_capture_on_commit_callbacks
    ) -> None:
        with django_capture_on_commit_callbacks(execute=True):
            registration = LearnerCourseRegistrationFactory()
        record = CourseProgress.objects.get(learner_registration=registration)
        CourseProgress.objects.filter(pk=record.pk).update(progress_percentage=42)

        with django_capture_on_commit_callbacks(execute=True):
            registration.save()

        assert CourseProgress.objects.count() == 1
        record.refresh_from_db()
        assert record.progress_percentage == 42

    def test_reactivating_a_registration_creates_no_second_record(
        self, mock_site_context, django_capture_on_commit_callbacks
    ) -> None:
        with django_capture_on_commit_callbacks(execute=True):
            registration = LearnerCourseRegistrationFactory()
        record = CourseProgress.objects.get(learner_registration=registration)
        CourseProgress.objects.filter(pk=record.pk).update(progress_percentage=42)

        registration.is_active = False
        registration.save()
        with django_capture_on_commit_callbacks(execute=True):
            registration.is_active = True
            registration.save()

        assert CourseProgress.objects.count() == 1
        record.refresh_from_db()
        assert record.progress_percentage == 42

    def test_re_adding_a_cohort_member_creates_no_second_record(
        self, mock_site_context, django_capture_on_commit_callbacks
    ) -> None:
        cohort = CohortFactory()
        CohortCourseRegistrationFactory(cohort=cohort)
        with django_capture_on_commit_callbacks(execute=True):
            membership = CohortMembershipFactory(cohort=cohort)
        record = CourseProgress.objects.get(learner=membership.learner)
        CourseProgress.objects.filter(pk=record.pk).update(progress_percentage=42)

        with django_capture_on_commit_callbacks(execute=True):
            membership.save()

        assert CourseProgress.objects.count() == 1
        record.refresh_from_db()
        assert record.progress_percentage == 42


@pytest.mark.django_db
class TestNothingRetiresARecord:
    """Removal and deactivation are access decisions; the work stays recorded."""

    def test_deleting_a_membership_leaves_the_record(
        self, mock_site_context, django_capture_on_commit_callbacks
    ) -> None:
        cohort = CohortFactory()
        CohortCourseRegistrationFactory(cohort=cohort)
        with django_capture_on_commit_callbacks(execute=True):
            membership = CohortMembershipFactory(cohort=cohort)

        with django_capture_on_commit_callbacks(execute=True):
            CohortMembership.objects.filter(pk=membership.pk).delete()

        assert CourseProgress.objects.filter(learner=membership.learner).exists()

    def test_deactivating_a_registration_leaves_the_record(
        self, mock_site_context, django_capture_on_commit_callbacks
    ) -> None:
        with django_capture_on_commit_callbacks(execute=True):
            registration = LearnerCourseRegistrationFactory()
        record = CourseProgress.objects.get(learner_registration=registration)
        CourseProgress.objects.filter(pk=record.pk).update(progress_percentage=42)

        with django_capture_on_commit_callbacks(execute=True):
            registration.is_active = False
            registration.save()

        record.refresh_from_db()
        assert record.progress_percentage == 42

    def test_deactivating_a_learner_leaves_the_record(
        self, mock_site_context, django_capture_on_commit_callbacks
    ) -> None:
        with django_capture_on_commit_callbacks(execute=True):
            registration = LearnerCourseRegistrationFactory()
        record = CourseProgress.objects.get(learner_registration=registration)

        with django_capture_on_commit_callbacks(execute=True):
            learner = registration.learner
            learner.is_active = False
            learner.save()

        assert CourseProgress.objects.filter(pk=record.pk).exists()


@pytest.mark.django_db
class TestRawSavesCreateNothing:
    """A fixture load writes exactly its own rows; deriving records from one
    would invent data the fixture author did not ask for."""

    def test_raw_learner_registration_creates_nothing(
        self, mock_site_context, django_capture_on_commit_callbacks
    ) -> None:
        registration: LearnerCourseRegistration = LearnerCourseRegistrationFactory()
        serialized = serializers.serialize("json", [registration])
        LearnerCourseRegistration.objects.filter(pk=registration.pk).delete()

        with django_capture_on_commit_callbacks(execute=True):
            for deserialized in serializers.deserialize("json", serialized):
                deserialized.save()

        assert not CourseProgress.objects.exists()

    def test_raw_cohort_registration_creates_nothing(
        self, mock_site_context, django_capture_on_commit_callbacks
    ) -> None:
        cohort = CohortFactory()
        CohortMembershipFactory(cohort=cohort)
        registration: CohortCourseRegistration = CohortCourseRegistrationFactory(
            cohort=cohort
        )
        serialized = serializers.serialize("json", [registration])
        CohortCourseRegistration.objects.filter(pk=registration.pk).delete()

        with django_capture_on_commit_callbacks(execute=True):
            for deserialized in serializers.deserialize("json", serialized):
                deserialized.save()

        assert not CourseProgress.objects.exists()

    def test_raw_membership_creates_nothing(
        self, mock_site_context, django_capture_on_commit_callbacks
    ) -> None:
        cohort = CohortFactory()
        CohortCourseRegistrationFactory(cohort=cohort)
        membership: CohortMembership = CohortMembershipFactory(cohort=cohort)
        serialized = serializers.serialize("json", [membership])
        CohortMembership.objects.filter(pk=membership.pk).delete()

        with django_capture_on_commit_callbacks(execute=True):
            for deserialized in serializers.deserialize("json", serialized):
                deserialized.save()

        assert not CourseProgress.objects.exists()


@pytest.mark.django_db
class TestCourseRegisteredWebhook:
    def test_the_record_exists_before_the_event_fires(
        self, mock_site_context, django_capture_on_commit_callbacks
    ) -> None:
        """An integrator handed a course_progress_id can read the row it names."""
        readable_records: list[int] = []

        with (
            patch(
                "freedom_ls.webhooks.events.fire_webhook_event",
                side_effect=lambda *args: readable_records.append(
                    CourseProgress.objects.count()
                ),
            ),
            django_capture_on_commit_callbacks(execute=True),
        ):
            LearnerCourseRegistrationFactory()

        assert readable_records == [1]

    def test_the_event_carries_the_organisation_and_the_record(
        self, mock_site_context, django_capture_on_commit_callbacks
    ) -> None:
        with (
            patch("freedom_ls.webhooks.events.fire_webhook_event") as mock_fire,
            django_capture_on_commit_callbacks(execute=True),
        ):
            registration = LearnerCourseRegistrationFactory()

        record = CourseProgress.objects.get(learner_registration=registration)
        _, payload = mock_fire.call_args.args
        assert payload["organisation_id"] == str(registration.learner.organisation_id)
        assert payload["course_progress_id"] == str(record.id)

    def test_the_record_is_still_created_with_no_ambient_request(
        self, mock_site_context, django_capture_on_commit_callbacks
    ) -> None:
        """A management command has no request for the site-aware manager to read."""
        from freedom_ls.site_aware_models.models import _thread_locals

        learner = LearnerFactory()
        course = CourseFactory()
        registration = LearnerCourseRegistration(learner=learner, collection=course)
        registration.site = mock_site_context

        request = _thread_locals.request
        del _thread_locals.request
        try:
            with django_capture_on_commit_callbacks(execute=True):
                registration.save()
        finally:
            _thread_locals.request = request

        assert CourseProgress._base_manager.filter(
            learner_registration=registration
        ).exists()
