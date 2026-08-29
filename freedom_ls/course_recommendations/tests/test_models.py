"""Tests for the RecommendedCourse model."""

from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_recommendations.factories import RecommendedCourseFactory


@pytest.mark.django_db
def test_str_names_the_user_and_the_course(mock_site_context):
    """__str__ identifies the recommendation by learner email and course title."""
    user = UserFactory(email="ada@example.com")
    course = CourseFactory(title="Intro to Beekeeping")

    recommendation = RecommendedCourseFactory(user=user, course=course)

    assert str(recommendation) == (
        "Course recommendation for ada@example.com: Intro to Beekeeping"
    )
