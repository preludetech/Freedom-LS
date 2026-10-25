"""Registering a user for a course deletes their recommendation for it."""

from __future__ import annotations

import pytest

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_recommendations.factories import RecommendedCourseFactory
from freedom_ls.course_recommendations.models import RecommendedCourse
from freedom_ls.course_recommendations.signals import clear_on_learner_reactivation
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

pytestmark = pytest.mark.django_db


def test_saving_an_active_individual_registration_deletes_the_recommendation(
    mock_site_context,
):
    learner = LearnerFactory()
    registration = LearnerCourseRegistrationFactory.build(
        learner=learner, course=CourseFactory()
    )
    RecommendedCourseFactory(user=learner.user, course=registration.course)

    registration.save()

    assert not RecommendedCourse.objects.filter(user=learner.user).exists()


def test_saving_an_inactive_individual_registration_keeps_the_recommendation(
    mock_site_context,
):
    learner = LearnerFactory()
    registration = LearnerCourseRegistrationFactory.build(
        learner=learner, course=CourseFactory(), is_active=False
    )
    RecommendedCourseFactory(user=learner.user, course=registration.course)

    registration.save()

    assert RecommendedCourse.objects.filter(user=learner.user).exists()


def test_reactivating_an_individual_registration_deletes_the_recommendation(
    mock_site_context,
):
    registration = LearnerCourseRegistrationFactory(is_active=False)
    user = registration.learner.user
    RecommendedCourseFactory(user=user, course=registration.course)

    registration = LearnerCourseRegistration.objects.get(pk=registration.pk)
    registration.is_active = True
    registration.save()

    assert not RecommendedCourse.objects.filter(user=user).exists()


def test_saving_a_cohort_registration_deletes_each_members_recommendation(
    mock_site_context,
):
    membership = CohortMembershipFactory()
    registration = CohortCourseRegistrationFactory.build(
        cohort=membership.cohort, course=CourseFactory()
    )
    user = membership.learner.user
    RecommendedCourseFactory(user=user, course=registration.course)

    registration.save()

    assert not RecommendedCourse.objects.filter(user=user).exists()


def test_saving_an_inactive_cohort_registration_keeps_the_recommendation(
    mock_site_context,
):
    membership = CohortMembershipFactory()
    registration = CohortCourseRegistrationFactory.build(
        cohort=membership.cohort, course=CourseFactory(), is_active=False
    )
    user = membership.learner.user
    RecommendedCourseFactory(user=user, course=registration.course)

    registration.save()

    assert RecommendedCourse.objects.filter(user=user).exists()


def test_joining_a_cohort_that_holds_the_course_deletes_the_recommendation(
    mock_site_context,
):
    cohort = CohortFactory()
    registration = CohortCourseRegistrationFactory(cohort=cohort)
    learner = LearnerFactory(organisation=cohort.organisation)
    RecommendedCourseFactory(user=learner.user, course=registration.course)

    CohortMembership.objects.create(cohort=cohort, learner=learner)

    assert not RecommendedCourse.objects.filter(user=learner.user).exists()


def test_reactivating_a_cohort_deletes_its_members_recommendations(mock_site_context):
    membership = CohortMembershipFactory()
    registration = CohortCourseRegistrationFactory(cohort=membership.cohort)
    Cohort.objects.filter(pk=membership.cohort_id).update(is_active=False)
    user = membership.learner.user
    RecommendedCourseFactory(user=user, course=registration.course)

    cohort = Cohort.objects.get(pk=membership.cohort_id)
    cohort.is_active = True
    cohort.save()

    assert not RecommendedCourse.objects.filter(user=user).exists()


def test_saving_an_inactive_cohort_keeps_recommendations(mock_site_context):
    membership = CohortMembershipFactory()
    registration = CohortCourseRegistrationFactory(cohort=membership.cohort)
    Cohort.objects.filter(pk=membership.cohort_id).update(is_active=False)
    user = membership.learner.user
    RecommendedCourseFactory(user=user, course=registration.course)

    cohort = Cohort.objects.get(pk=membership.cohort_id)
    cohort.name = "Renamed"
    cohort.save()

    assert RecommendedCourse.objects.filter(user=user).exists()


def test_reactivating_a_learner_deletes_the_recommendation(mock_site_context):
    learner = LearnerFactory(is_active=False)
    registration = LearnerCourseRegistrationFactory(learner=learner)
    RecommendedCourseFactory(user=learner.user, course=registration.course)

    learner = Learner.objects.get(pk=learner.pk)
    learner.is_active = True
    learner.save()

    assert not RecommendedCourse.objects.filter(user=learner.user).exists()


def test_saving_an_inactive_learner_keeps_the_recommendation(mock_site_context):
    learner = LearnerFactory(is_active=False)
    registration = LearnerCourseRegistrationFactory(learner=learner)
    RecommendedCourseFactory(user=learner.user, course=registration.course)

    learner = Learner.objects.get(pk=learner.pk)
    learner.save()

    assert RecommendedCourse.objects.filter(user=learner.user).exists()


def test_a_learner_save_that_leaves_is_active_out_of_update_fields_runs_no_query(
    mock_site_context, django_assert_num_queries
):
    learner = LearnerFactory(is_active=False)
    learner = Learner.objects.get(pk=learner.pk)
    learner.is_active = True

    with django_assert_num_queries(0):
        clear_on_learner_reactivation(
            sender=Learner,
            instance=learner,
            update_fields=frozenset({"organisation"}),
        )


def test_a_raw_save_deletes_nothing(mock_site_context):
    registration = LearnerCourseRegistrationFactory(is_active=False)
    user = registration.learner.user
    RecommendedCourseFactory(user=user, course=registration.course)

    registration.is_active = True
    LearnerCourseRegistration.save_base(registration, raw=True)

    assert RecommendedCourse.objects.filter(user=user).exists()
