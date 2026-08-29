"""get_recommended_courses: whose recommendations a learner is shown."""

from __future__ import annotations

import pytest

from django.contrib.auth.models import AnonymousUser

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_recommendations.factories import RecommendedCourseFactory
from freedom_ls.course_recommendations.queries import get_recommended_courses

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
