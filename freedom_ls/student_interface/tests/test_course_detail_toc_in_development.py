"""Behaviour tests for the ``table_of_contents_in_development`` course flag.

Covers the three TOC surfaces on the course detail page (Lessons stat card,
"This course includes" panel, "Course content" section) being omitted while
a course's contents are still being built.
"""

from __future__ import annotations

import pytest

from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
def test_toc_in_development_hides_all_three_surfaces(
    mock_site_context, course_with_topic
):
    """Flag on, no assessments, no certificate: no TOC surface renders at all."""
    course = course_with_topic(
        access_type="free", table_of_contents_in_development=True
    )
    client = Client()

    url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)
    content = response.content.decode()

    assert response.status_code == 200
    assert course.title in content
    assert "Lessons" not in content
    assert "This course includes" not in content
    assert "Course content" not in content


@pytest.mark.django_db
def test_toc_in_development_with_assessments_shows_only_assessments_line(
    mock_site_context, course_with_topic
):
    """Flag on with assessments: panel shows only 'Includes assessments'."""
    from freedom_ls.content_engine.factories import FormFactory

    course = course_with_topic(
        access_type="free", table_of_contents_in_development=True
    )
    course.items.create(child=FormFactory(), order=1)
    client = Client()

    url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)
    content = response.content.decode()

    assert response.status_code == 200
    assert "This course includes" in content
    assert "Includes assessments" in content
    assert "Lessons" not in content
    assert "1 lesson" not in content
    assert "Course content" not in content


@pytest.mark.django_db
def test_toc_in_development_off_shows_all_three_surfaces(
    mock_site_context, course_with_topic
):
    """Flag omitted (default False): page renders exactly as before — all three surfaces present."""
    course = course_with_topic(access_type="free")
    client = Client()

    url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": course.slug}
    )
    response = client.get(url)
    content = response.content.decode()

    assert response.status_code == 200
    assert "Lessons" in content
    assert "This course includes" in content
    assert "1 lesson" in content
    assert "Course content" in content
