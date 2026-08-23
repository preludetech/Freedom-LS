"""Tests for CourseInterestAdmin.

A read surface only -- no custom admin actions, no delete-permission
override. These tests cover the changelist rendering, search, the surfaced
timestamp and site isolation.

Assertions about which rows the changelist holds go through
``response.context["cl"].result_list`` rather than raw page content: the
rendered page also carries an unrelated Unfold navigation listing every
course, so a substring check would pass or fail on that listing rather than
on the admin.
"""

from __future__ import annotations

import pytest
import time_machine

from django.urls import reverse

from freedom_ls.accounts.factories import SiteFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_interest.factories import CourseInterestFactory

CHANGELIST_URL_NAME = "admin:freedom_ls_course_interest_courseinterest_changelist"


@pytest.mark.django_db
class TestCourseInterestAdminChangelist:
    def test_changelist_lists_an_expressed_interest(self, staff_client):
        interest = CourseInterestFactory(
            course=CourseFactory(title="Advanced Piloting")
        )

        response = staff_client.get(reverse(CHANGELIST_URL_NAME))

        assert list(response.context["cl"].result_list) == [interest]

    def test_changelist_shows_when_the_interest_was_expressed(self, staff_client):
        """The timestamp is the column the educator-facing panel this admin
        replaced was read for -- a listing without it answers nothing."""
        with time_machine.travel("2024-06-01 12:00:00+00:00", tick=False):
            CourseInterestFactory(course=CourseFactory(title="Advanced Piloting"))

        response = staff_client.get(reverse(CHANGELIST_URL_NAME))

        assert "June 1, 2024" in response.content.decode()

    def test_changelist_excludes_interest_expressed_on_another_site(self, staff_client):
        own_site_interest = CourseInterestFactory(
            course=CourseFactory(title="Advanced Piloting")
        )
        CourseInterestFactory(
            course=CourseFactory(title="Beginner Navigation"), site=SiteFactory()
        )

        response = staff_client.get(reverse(CHANGELIST_URL_NAME))

        assert list(response.context["cl"].result_list) == [own_site_interest]

    def test_changelist_search_finds_interest_by_course_title(self, staff_client):
        course = CourseFactory(title="Advanced Piloting")
        matching = CourseInterestFactory(course=course)
        CourseInterestFactory(course=CourseFactory(title="Beginner Navigation"))

        response = staff_client.get(
            reverse(CHANGELIST_URL_NAME), {"q": "Advanced Piloting"}
        )

        assert list(response.context["cl"].result_list) == [matching]
