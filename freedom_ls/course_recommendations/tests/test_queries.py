"""get_recommended_courses and clear_registered_recommendations."""

from __future__ import annotations

import pytest

from django.contrib.auth.models import AnonymousUser

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_recommendations.factories import RecommendedCourseFactory
from freedom_ls.course_recommendations.models import RecommendedCourse
from freedom_ls.course_recommendations.queries import (
    clear_registered_recommendations,
    get_recommended_courses,
)
from freedom_ls.learner_management.factories import (
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.tests.site_context import drop_ambient_request, site_context

pytestmark = pytest.mark.django_db


def test_an_anonymous_visitor_has_no_recommendations(mock_site_context):
    assert list(get_recommended_courses(AnonymousUser())) == []


def test_a_user_with_nothing_recommended_gets_an_empty_list(mock_site_context):
    assert list(get_recommended_courses(UserFactory())) == []


def test_every_course_recommended_to_the_user_is_returned(mock_site_context):
    user = UserFactory()
    courses = CourseFactory.create_batch(2)
    RecommendedCourseFactory(user=user, course=courses[0])
    RecommendedCourseFactory(user=user, course=courses[1])

    result = get_recommended_courses(user)

    assert sorted(r.course.pk for r in result) == sorted(c.pk for c in courses)


def test_another_users_recommendations_are_not_returned(mock_site_context):
    user = UserFactory()
    courses = CourseFactory.create_batch(2)
    RecommendedCourseFactory(user=user, course=courses[0])
    RecommendedCourseFactory(user=UserFactory(), course=courses[1])

    result = get_recommended_courses(user)

    assert [r.course for r in result] == [courses[0]]


# --- clear_registered_recommendations ------------------------------------------


@pytest.mark.django_db
def test_clearing_deletes_a_recommendation_for_a_registered_course(mock_site_context):
    registration = LearnerCourseRegistrationFactory()
    user = registration.learner.user
    RecommendedCourseFactory(user=user, course=registration.course)

    clear_registered_recommendations(mock_site_context.pk, [user.pk])

    assert not RecommendedCourse.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_clearing_keeps_a_recommendation_for_an_unregistered_course(mock_site_context):
    registration = LearnerCourseRegistrationFactory()
    user = registration.learner.user
    kept = RecommendedCourseFactory(user=user)

    clear_registered_recommendations(mock_site_context.pk, [user.pk])

    assert list(RecommendedCourse.objects.filter(user=user)) == [kept]


@pytest.mark.django_db
def test_clearing_returns_the_number_of_recommendations_deleted(mock_site_context):
    learner = LearnerFactory()
    registrations = LearnerCourseRegistrationFactory.create_batch(2, learner=learner)
    for registration in registrations:
        RecommendedCourseFactory(user=learner.user, course=registration.course)
    RecommendedCourseFactory(user=learner.user)

    deleted = clear_registered_recommendations(mock_site_context.pk, [learner.user_id])

    assert deleted == 2


@pytest.mark.django_db
def test_clearing_leaves_another_sites_recommendations(mock_site_context):
    registration = LearnerCourseRegistrationFactory()
    user = registration.learner.user
    other_site = SiteFactory()
    with site_context(other_site):
        other = RecommendedCourseFactory(user=user, course=registration.course)
    drop_ambient_request()

    clear_registered_recommendations(mock_site_context.pk, [user.pk])

    assert RecommendedCourse._base_manager.filter(pk=other.pk).exists()
