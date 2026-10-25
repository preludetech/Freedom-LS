"""Tests for the RecommendedCourse model."""

from __future__ import annotations

import pytest

from django.db import IntegrityError, transaction

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_recommendations.factories import RecommendedCourseFactory
from freedom_ls.course_recommendations.models import RecommendedCourse
from freedom_ls.tests.factories import SiteFactory


@pytest.mark.django_db
def test_str_names_the_user_and_the_course(mock_site_context):
    """__str__ identifies the recommendation by learner email and course title."""
    user = UserFactory(email="ada@example.com")
    course = CourseFactory(title="Intro to Beekeeping")

    recommendation = RecommendedCourseFactory(user=user, course=course)

    assert str(recommendation) == (
        "Course recommendation for ada@example.com: Intro to Beekeeping"
    )


@pytest.mark.django_db
def test_a_user_cannot_hold_two_recommendations_for_one_course(mock_site_context):
    user = UserFactory()
    course = CourseFactory()
    RecommendedCourseFactory(user=user, course=course)

    with (
        pytest.raises(IntegrityError, match="unique_recommended_course"),
        transaction.atomic(),
    ):
        RecommendedCourseFactory(user=user, course=course)


@pytest.mark.django_db
def test_two_sites_may_recommend_the_same_course_to_the_same_user(mock_site_context):
    user = UserFactory()
    course = CourseFactory()
    other_site = SiteFactory(domain="other.example.com", name="Other")
    RecommendedCourseFactory(user=user, course=course)

    RecommendedCourse.objects.create(user=user, course=course, site=other_site)

    assert RecommendedCourse._base_manager.filter(user=user, course=course).count() == 2
