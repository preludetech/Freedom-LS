"""Tests for the RecommendedCourse model."""

from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_recommendations.factories import RecommendedCourseFactory
from freedom_ls.course_recommendations.models import RecommendedCourse


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
def test_recommendations_for_another_site_not_returned_in_current_site(
    mock_site_context,
):
    """Cross-tenant isolation: rows from another site are filtered out."""
    other_site = SiteFactory(name="OtherSite")

    visible_course = CourseFactory(title="Visible Course")
    RecommendedCourseFactory(course=visible_course)

    hidden_course = CourseFactory(title="Hidden Course", site=other_site)
    other_user = UserFactory(site=other_site)
    RecommendedCourseFactory(user=other_user, course=hidden_course, site=other_site)

    titles = list(RecommendedCourse.objects.values_list("course__title", flat=True))
    assert titles == ["Visible Course"]


@pytest.mark.django_db
def test_site_set_automatically_on_create(mock_site_context, site):
    """site_id comes from the current site context, never from the caller."""
    recommendation = RecommendedCourseFactory()

    assert recommendation.site == site
