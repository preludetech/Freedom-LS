"""Tests for ensure_course_progress_record and the cohort fan-out.

Mirrors test_ensure_learner.py's shape: the idempotent get-or-create half and
the site provenance it must not get from the ambient request.
"""

from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import SiteFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.learner_progress.utils import (
    ensure_course_progress_record,
    ensure_course_progress_records_for_cohort_registration,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.site_aware_models.models import _thread_locals


@pytest.mark.django_db
class TestEnsureCourseProgressRecord:
    def test_calling_twice_creates_one_record(self, mock_site_context):
        course = CourseFactory()
        learner = LearnerFactory()
        registration = LearnerCourseRegistrationFactory(learner=learner, course=course)

        ensure_course_progress_record(learner, course, registration)
        ensure_course_progress_record(learner, course, registration)

        assert (
            CourseProgress.objects.filter(
                learner=learner, learner_registration=registration
            ).count()
            == 1
        )

    def test_calling_twice_returns_the_same_row(self, mock_site_context):
        course = CourseFactory()
        learner = LearnerFactory()
        registration = LearnerCourseRegistrationFactory(learner=learner, course=course)

        first = ensure_course_progress_record(learner, course, registration)
        second = ensure_course_progress_record(learner, course, registration)

        assert first.pk == second.pk

    def test_an_existing_record_is_returned_untouched(self, mock_site_context):
        """No timestamp reset and no grant re-pointing -- the idempotency rule
        is "leave it alone", so get_or_create and not update_or_create."""
        course = CourseFactory()
        learner = LearnerFactory()
        registration = LearnerCourseRegistrationFactory(learner=learner, course=course)
        existing = ensure_course_progress_record(learner, course, registration)
        existing.progress_percentage = 42
        existing.save(update_fields=["progress_percentage"])

        returned = ensure_course_progress_record(learner, course, registration)

        assert returned.pk == existing.pk
        assert returned.progress_percentage == 42

    def test_a_second_registration_mints_a_second_record(self, mock_site_context):
        """Idempotent on the registration, not on (learner, course): a
        learner already holding a cohort-granted record who is then
        registered individually gets a second record, because a second grant
        is a second enrolment."""
        organisation = OrganisationFactory()
        course = CourseFactory()
        cohort = CohortFactory(organisation=organisation)
        learner = LearnerFactory(organisation=organisation)
        CohortMembershipFactory(learner=learner, cohort=cohort)
        cohort_registration = CohortCourseRegistrationFactory(
            cohort=cohort, course=course
        )
        individual_registration = LearnerCourseRegistrationFactory(
            learner=learner, course=course
        )

        ensure_course_progress_record(learner, course, cohort_registration)
        ensure_course_progress_record(learner, course, individual_registration)

        assert CourseProgress.objects.filter(learner=learner).count() == 2

    def test_raises_when_the_registration_is_for_a_different_course(
        self, mock_site_context
    ):
        course = CourseFactory()
        other_course = CourseFactory()
        learner = LearnerFactory()
        registration = LearnerCourseRegistrationFactory(
            learner=learner, course=other_course
        )

        with pytest.raises(ValueError, match="must be for the course"):
            ensure_course_progress_record(learner, course, registration)

    def test_site_comes_from_learner_site_with_no_ambient_request(
        self, mock_site_context
    ):
        """A management command, a bulk import or a signal fired under a
        foreign ambient site has no request to read the site from."""
        course = CourseFactory()
        learner = LearnerFactory()
        registration = LearnerCourseRegistrationFactory(learner=learner, course=course)

        del _thread_locals.request
        record = ensure_course_progress_record(learner, course, registration)

        assert record.site_id == learner.site_id

    def test_site_comes_from_learner_site_under_a_foreign_ambient_site(
        self, mock_site_context
    ):
        """The learner is not always in the site the current request is for.
        Using the site-aware manager for the lookup half of get_or_create
        would AND the ambient site onto the query, miss the row created
        below, and attempt a second INSERT -- raising IntegrityError on
        one_course_progress_per_learner_registration."""
        organisation = OrganisationFactory(site=SiteFactory())
        learner = LearnerFactory(organisation=organisation)
        course = CourseFactory()
        registration = LearnerCourseRegistrationFactory(learner=learner, course=course)

        first = ensure_course_progress_record(learner, course, registration)
        second = ensure_course_progress_record(learner, course, registration)

        assert first.pk == second.pk
        assert first.site_id == learner.site_id
        assert first.site_id != mock_site_context.id
        assert (
            CourseProgress._base_manager.filter(
                learner=learner, learner_registration=registration
            ).count()
            == 1
        )


@pytest.mark.django_db
class TestEnsureCourseProgressRecordsForCohortRegistration:
    def test_covers_exactly_the_active_members(self, mock_site_context):
        organisation = OrganisationFactory()
        course = CourseFactory()
        cohort = CohortFactory(organisation=organisation)
        active_learner = LearnerFactory(organisation=organisation)
        removed_learner = LearnerFactory(organisation=organisation, is_active=False)
        CohortMembershipFactory(learner=active_learner, cohort=cohort)
        CohortMembershipFactory(learner=removed_learner, cohort=cohort)
        registration = CohortCourseRegistrationFactory(cohort=cohort, course=course)

        ensure_course_progress_records_for_cohort_registration(registration)

        records = CourseProgress.objects.filter(cohort_registration=registration)
        assert set(records.values_list("learner_id", flat=True)) == {active_learner.id}

    def test_site_comes_from_each_members_learner_site_under_a_foreign_ambient_site(
        self, mock_site_context
    ):
        """The bulk_create bypasses save(), so it has no _set_site_from_request
        to fall back on either -- every record it mints must carry its own
        member's site, not whatever site the request happens to be for."""
        organisation = OrganisationFactory(site=SiteFactory())
        course = CourseFactory()
        cohort = CohortFactory(organisation=organisation)
        learner = LearnerFactory(organisation=organisation)
        CohortMembershipFactory(learner=learner, cohort=cohort)
        registration = CohortCourseRegistrationFactory(cohort=cohort, course=course)

        ensure_course_progress_records_for_cohort_registration(registration)

        record = CourseProgress._base_manager.get(
            learner=learner, cohort_registration=registration
        )
        assert record.site_id == learner.site_id
        assert record.site_id != mock_site_context.id

    def test_a_member_added_later_gets_a_record_when_re_run(self, mock_site_context):
        organisation = OrganisationFactory()
        course = CourseFactory()
        cohort = CohortFactory(organisation=organisation)
        first_learner = LearnerFactory(organisation=organisation)
        CohortMembershipFactory(learner=first_learner, cohort=cohort)
        registration = CohortCourseRegistrationFactory(cohort=cohort, course=course)
        ensure_course_progress_records_for_cohort_registration(registration)

        second_learner = LearnerFactory(organisation=organisation)
        CohortMembershipFactory(learner=second_learner, cohort=cohort)
        ensure_course_progress_records_for_cohort_registration(registration)

        records = CourseProgress.objects.filter(cohort_registration=registration)
        assert set(records.values_list("learner_id", flat=True)) == {
            first_learner.id,
            second_learner.id,
        }
