"""Tests for the player breadcrumb trail's first crumb destination."""

import re

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.student_management.factories import UserCourseRegistrationFactory


def _breadcrumb_nav(html: str) -> str:
    """Extract the breadcrumb <nav>...</nav> block from a rendered player page."""
    match = re.search(r'<nav aria-label="Breadcrumb">.*?</nav>', html, flags=re.DOTALL)
    assert match is not None, "breadcrumb <nav> not found in response"
    return match.group(0)


@pytest.mark.django_db
def test_first_crumb_links_to_course_detail_not_item_one(mock_site_context):
    course = CourseFactory(title="Breadcrumb Course", slug="breadcrumb-course")
    topic = TopicFactory(title="Only Topic", slug="only-topic", content="x")
    course.items.create(child=topic, order=0)
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=course)

    client = Client()
    client.force_login(user)
    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": "breadcrumb-course", "index": 1},
    )
    response = client.get(url)
    assert response.status_code == 200

    nav_html = _breadcrumb_nav(response.content.decode())

    course_detail_url = reverse(
        "student_interface:course_detail", kwargs={"course_slug": "breadcrumb-course"}
    )
    item_one_url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": "breadcrumb-course", "index": 1},
    )

    assert f'href="{course_detail_url}"' in nav_html
    assert f'href="{item_one_url}"' not in nav_html
