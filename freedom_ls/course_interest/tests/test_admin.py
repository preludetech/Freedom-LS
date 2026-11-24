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

from django.contrib.admin.widgets import AutocompleteSelect
from django.core.exceptions import NON_FIELD_ERRORS
from django.forms import Select
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_interest.factories import CourseInterestFactory
from freedom_ls.course_interest.forms import CourseInterestAdminForm
from freedom_ls.course_interest.models import CourseInterest
from freedom_ls.tests.factories import SiteFactory

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


# CourseInterestAdminForm
#
# SiteAwareModelAdmin excludes ``site`` from every admin form, and
# UniqueConstraint.validate() abandons a constraint whose field sits in that
# exclusion set. CourseInterestAdminForm un-excludes ``site`` so a duplicate
# interest surfaces as a form error instead of an IntegrityError.


@pytest.mark.django_db
def test_admin_form_rejects_duplicate_user_course_pair(
    mock_site_context,
):
    interest = CourseInterestFactory()

    form = CourseInterestAdminForm(
        data={"user": interest.user_id, "course": interest.course_id}
    )

    assert form.is_valid() is False
    assert NON_FIELD_ERRORS in form.errors


@pytest.mark.django_db
def test_add_form_picks_the_course_with_a_plain_select(staff_client: Client) -> None:
    response = staff_client.get(
        reverse("admin:freedom_ls_course_interest_courseinterest_add")
    )

    widget = response.context["adminform"].form.fields["course"].widget.widget
    assert isinstance(widget, Select)
    assert not isinstance(widget, AutocompleteSelect)


@pytest.mark.django_db
def test_add_post_saves_the_interest_for_the_posted_course_pk(
    staff_client: Client,
) -> None:
    course = CourseFactory()
    user = UserFactory()

    response = staff_client.post(
        reverse("admin:freedom_ls_course_interest_courseinterest_add"),
        {"user": user.pk, "course": course.pk},
    )

    assert response.status_code == 302
    assert CourseInterest.objects.get().course == course
