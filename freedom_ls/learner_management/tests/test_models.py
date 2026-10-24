from __future__ import annotations

import pytest

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.utils import is_registered_for_course
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.utils import get_default_organisation


# Self-registration through initiate_course_access (the chokepoint for
# self-service course access) keys on Learner: the Learner it creates, its
# idempotence, and reactivation of a removed learner. The backend-branching
# coverage (gated vs free, GET vs POST) is in learner_interface views.
def _initiate_course_access_url(course_slug: str) -> str:
    return reverse(
        "learner_interface:initiate_course_access", kwargs={"course_slug": course_slug}
    )


@pytest.mark.django_db
def test_self_registering_creates_a_learner_on_the_default_organisation(
    mock_site_context, site, logged_in_client, course_with_topic
):
    course = course_with_topic(access_type="free")
    user = UserFactory()
    client = logged_in_client(user)

    client.post(_initiate_course_access_url(course.slug))

    default_organisation = get_default_organisation(site)
    learner = Learner.objects.get(user=user, organisation=default_organisation)
    assert learner.is_active is True
    assert LearnerCourseRegistration.objects.filter(
        learner=learner, course=course, is_active=True
    ).exists()


@pytest.mark.django_db
def test_self_registering_twice_creates_one_learner_and_one_registration(
    mock_site_context, site, logged_in_client, course_with_topic
):
    course = course_with_topic(access_type="free")
    user = UserFactory()
    client = logged_in_client(user)
    url = _initiate_course_access_url(course.slug)

    client.post(url)
    client.post(url)

    default_organisation = get_default_organisation(site)
    assert (
        Learner.objects.filter(user=user, organisation=default_organisation).count()
        == 1
    )
    assert (
        LearnerCourseRegistration.objects.filter(
            learner__user=user, course=course
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_self_registering_reactivates_a_removed_learner(
    mock_site_context, site, logged_in_client, course_with_topic
):
    course = course_with_topic(access_type="free")
    user = UserFactory()
    default_organisation = get_default_organisation(site)
    LearnerFactory(user=user, organisation=default_organisation, is_active=False)
    client = logged_in_client(user)
    assert is_registered_for_course(user, course) is False

    client.post(_initiate_course_access_url(course.slug))

    learner = Learner.objects.get(user=user, organisation=default_organisation)
    assert learner.is_active is True
    assert is_registered_for_course(user, course) is True


@pytest.mark.django_db
def test_self_registering_reactivates_a_deactivated_registration(
    mock_site_context, site, logged_in_client, course_with_topic
):
    """An admin may deactivate the registration rather than the Learner.
    Re-registering has to restore access: finding the row and leaving it
    inactive dead-ends the learner, since course_home then bounces them
    straight back to the course detail page."""
    course = course_with_topic(access_type="free")
    user = UserFactory()
    learner = LearnerFactory(user=user, organisation=get_default_organisation(site))
    LearnerCourseRegistrationFactory(learner=learner, course=course, is_active=False)
    client = logged_in_client(user)
    assert is_registered_for_course(user, course) is False

    client.post(_initiate_course_access_url(course.slug))

    assert is_registered_for_course(user, course) is True


@pytest.mark.django_db
def test_self_registering_marks_a_new_registration_as_self_registered(
    mock_site_context, logged_in_client, course_with_topic
) -> None:
    course = course_with_topic(access_type="free")
    user = UserFactory()
    client = logged_in_client(user)

    client.post(_initiate_course_access_url(course.slug))

    assert LearnerCourseRegistration.objects.get(
        learner__user=user, course=course
    ).self_registered


@pytest.mark.django_db
def test_reactivating_an_admin_registration_leaves_it_marked_as_not_self_registered(
    mock_site_context, site, logged_in_client, course_with_topic
) -> None:
    course = course_with_topic(access_type="free")
    user = UserFactory()
    learner = LearnerFactory(user=user, organisation=get_default_organisation(site))
    LearnerCourseRegistrationFactory(learner=learner, course=course, is_active=False)
    client = logged_in_client(user)

    client.post(_initiate_course_access_url(course.slug))

    assert not LearnerCourseRegistration.objects.get(
        learner=learner, course=course
    ).self_registered


# Tests for the enrolment models and their Learner relations.


@pytest.mark.django_db
class TestCohortMembershipClean:
    def test_rejects_a_learner_and_cohort_in_different_organisations(
        self, mock_site_context
    ):
        learner = LearnerFactory(organisation=OrganisationFactory())
        cohort = CohortFactory(
            organisation=OrganisationFactory(), name="Year 10 Science"
        )

        membership = CohortMembership(learner=learner, cohort=cohort)

        with pytest.raises(ValidationError):
            membership.clean()

    def test_permits_a_learner_and_cohort_in_the_same_organisation(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)
        cohort = CohortFactory(organisation=organisation, name="Year 10 Maths")

        membership = CohortMembership(learner=learner, cohort=cohort)

        membership.clean()

    def test_does_not_raise_when_learner_is_unset(self, mock_site_context):
        cohort = CohortFactory(organisation=OrganisationFactory())

        membership = CohortMembership(cohort=cohort)

        membership.clean()

    def test_does_not_raise_when_cohort_is_unset(self, mock_site_context):
        learner = LearnerFactory(organisation=OrganisationFactory())

        membership = CohortMembership(learner=learner)

        membership.clean()


@pytest.mark.django_db
class TestCohortNameUniqueness:
    """Cohort names are unique per organisation, not per site: the same name may
    be used once in each organisation."""

    def test_two_cohorts_with_one_name_in_one_organisation_are_rejected(
        self, mock_site_context
    ):
        organisation = OrganisationFactory()
        CohortFactory(organisation=organisation, name="Year 10 Science")

        with pytest.raises(IntegrityError):
            CohortFactory(organisation=organisation, name="Year 10 Science")

    def test_the_same_cohort_name_in_two_organisations_is_permitted(
        self, mock_site_context
    ):
        CohortFactory(organisation=OrganisationFactory(), name="Year 10 Science")
        CohortFactory(organisation=OrganisationFactory(), name="Year 10 Science")

        assert Cohort.objects.filter(name="Year 10 Science").count() == 2


@pytest.mark.django_db
class TestLearnerCourseRegistrationUniqueness:
    """One learner per organisation, one registration each -- the same user
    can hold a registration in two organisations because each organisation
    gives them a distinct Learner row."""

    def test_two_registrations_for_one_learner_and_course_are_rejected(
        self, mock_site_context
    ):
        course = CourseFactory()
        learner = LearnerFactory()
        LearnerCourseRegistrationFactory(learner=learner, course=course)

        with pytest.raises(IntegrityError):
            LearnerCourseRegistrationFactory(learner=learner, course=course)

    def test_one_user_may_register_for_one_course_through_two_organisations(
        self, mock_site_context
    ):
        user = UserFactory()
        course = CourseFactory()
        learner_a = LearnerFactory(user=user, organisation=OrganisationFactory())
        learner_b = LearnerFactory(user=user, organisation=OrganisationFactory())
        LearnerCourseRegistrationFactory(learner=learner_a, course=course)
        LearnerCourseRegistrationFactory(learner=learner_b, course=course)

        assert (
            LearnerCourseRegistration.objects.filter(
                learner__user=user, course=course
            ).count()
            == 2
        )


@pytest.mark.django_db
class TestDeactivatingALearnerPreservesRecords:
    """Removal is soft and never cascades: every enrolment and progress row a
    removed learner held stays exactly as it was. Only access is suspended."""

    def test_the_course_registration_stays_active(self, mock_site_context):
        learner = LearnerFactory()
        registration = LearnerCourseRegistrationFactory(learner=learner)

        learner.is_active = False
        learner.save()

        registration.refresh_from_db()
        assert registration.is_active is True

    def test_the_cohort_membership_survives(self, mock_site_context):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)
        membership = CohortMembershipFactory(
            learner=learner, cohort=CohortFactory(organisation=organisation)
        )

        learner.is_active = False
        learner.save()

        assert CohortMembership.objects.filter(pk=membership.pk).exists()

    def test_access_to_the_registered_course_is_suspended(self, mock_site_context):
        course = CourseFactory()
        learner = LearnerFactory()
        LearnerCourseRegistrationFactory(learner=learner, course=course)

        learner.is_active = False
        learner.save()

        assert is_registered_for_course(learner.user, course) is False


# Tests for the Learner model.


@pytest.mark.django_db
class TestLearnerUniqueness:
    """Learner.objects.create, not LearnerFactory: the factory delegates to
    ensure_learner, which is idempotent by design and so can never produce the
    duplicate row these tests need."""

    def test_duplicate_user_and_organisation_is_rejected(self, mock_site_context):
        user = UserFactory()
        organisation = OrganisationFactory()
        Learner.objects.create(user=user, organisation=organisation)

        with pytest.raises(IntegrityError):
            Learner.objects.create(user=user, organisation=organisation)

    def test_same_user_may_hold_rows_in_two_organisations(self, mock_site_context):
        user = UserFactory()
        Learner.objects.create(user=user, organisation=OrganisationFactory())
        Learner.objects.create(user=user, organisation=OrganisationFactory())

        assert Learner.objects.filter(user=user).count() == 2


@pytest.mark.django_db
class TestLearnerSite:
    def test_learner_takes_its_site_from_its_organisation(self, mock_site_context):
        organisation = OrganisationFactory()

        learner = Learner.objects.create(user=UserFactory(), organisation=organisation)

        assert learner.site_id == organisation.site_id


# Deletion semantics for the registration models: registrations PROTECT their course.


@pytest.mark.django_db
class TestRegistrationCourseProtect:
    def test_deleting_a_course_with_a_learner_registration_is_blocked(
        self, mock_site_context
    ):
        registration = LearnerCourseRegistrationFactory()

        with pytest.raises(ProtectedError), transaction.atomic():
            registration.course.delete()

    def test_deleting_a_course_with_a_cohort_registration_is_blocked(
        self, mock_site_context
    ):
        registration = CohortCourseRegistrationFactory()

        with pytest.raises(ProtectedError), transaction.atomic():
            registration.course.delete()


@pytest.mark.django_db
def test_loaded_is_active_is_the_value_the_row_was_loaded_with(mock_site_context):
    registration = LearnerCourseRegistrationFactory(is_active=False)

    loaded = LearnerCourseRegistration.objects.get(pk=registration.pk)
    loaded.is_active = True

    assert loaded.loaded_is_active is False


@pytest.mark.django_db
def test_loaded_is_active_is_none_when_is_active_is_deferred(mock_site_context):
    registration = LearnerCourseRegistrationFactory()

    loaded = LearnerCourseRegistration.objects.defer("is_active").get(
        pk=registration.pk
    )

    assert loaded.loaded_is_active is None


@pytest.mark.django_db
def test_loaded_is_active_is_none_on_an_unsaved_instance(mock_site_context):
    registration = LearnerCourseRegistrationFactory.build()

    assert registration.loaded_is_active is None
