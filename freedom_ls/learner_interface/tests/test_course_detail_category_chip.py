"""The course detail hero shows a chip naming the course's dashboard_category."""

from __future__ import annotations

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.content_engine.factories import CourseCategoryFactory


@pytest.mark.django_db
def test_chip_shows_the_dashboard_category_title(mock_site_context, course_with_topic):
    category = CourseCategoryFactory(title="Data literacy")
    course = course_with_topic(access_type="free", dashboard_category=category)
    client = Client()

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    html = response.content.decode()
    assert 'data-testid="course-category-chip"' in html
    assert "Data literacy" in html


@pytest.mark.django_db
def test_chip_absent_when_dashboard_category_is_null(
    mock_site_context, course_with_topic
):
    course = course_with_topic(access_type="free")
    client = Client()

    url = reverse(
        "learner_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)

    assert 'data-testid="course-category-chip"' not in response.content.decode()
