"""Tests for CourseInterestAdmin.

A read surface only -- no custom admin actions, no delete-permission
override. These tests cover the changelist rendering and search, the two
things a hand-written admin class can get wrong.
"""

from __future__ import annotations

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_interest.factories import CourseInterestFactory

CHANGELIST_URL_NAME = "admin:freedom_ls_course_interest_courseinterest_changelist"


@pytest.fixture
def staff_client(mock_site_context, db):
    user = UserFactory(superuser=True)
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.django_db
class TestCourseInterestAdminChangelist:
    def test_changelist_lists_an_expressed_interest(self, staff_client):
        course = CourseFactory(title="Advanced Piloting")
        interest = CourseInterestFactory(course=course)

        response = staff_client.get(reverse(CHANGELIST_URL_NAME))

        assert response.status_code == 200
        content = response.content.decode()
        assert course.title in content
        assert interest.user.email in content

    def test_changelist_search_finds_interest_by_course_title(self, staff_client):
        """Scoped to the changelist's own result set -- the rendered page also
        carries an unrelated Unfold navigation listing every course, so
        asserting against raw page content would pass or fail on that
        listing rather than on the admin's search_fields."""
        course = CourseFactory(title="Advanced Piloting")
        matching = CourseInterestFactory(course=course)
        CourseInterestFactory(course=CourseFactory(title="Beginner Navigation"))

        response = staff_client.get(
            reverse(CHANGELIST_URL_NAME), {"q": "Advanced Piloting"}
        )

        assert list(response.context["cl"].result_list) == [matching]
