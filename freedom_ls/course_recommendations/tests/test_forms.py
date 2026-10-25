"""Tests for the RecommendedCourse admin form."""

from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_recommendations.models import RecommendedCourse


@pytest.mark.django_db
def test_adding_the_same_recommendation_twice_is_a_form_error(
    staff_client, mock_site_context
):
    user = UserFactory()
    course = CourseFactory()
    url = reverse("admin:freedom_ls_course_recommendations_recommendedcourse_add")
    data = {"user": user.pk, "course": course.pk}
    staff_client.post(url, data)

    response = staff_client.post(url, data)

    assert response.status_code == 200
    assert response.context["adminform"].form.non_field_errors()
    assert RecommendedCourse.objects.filter(user=user, course=course).count() == 1
