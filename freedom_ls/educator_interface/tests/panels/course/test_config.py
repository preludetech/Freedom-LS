"""Tests for the course section's configuration."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from django.contrib.sites.models import Site
from django.test import Client

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.tests.helpers import (
    _get_quick_view,
    _interface_url,
    course_per_reach_row,
    organisation_admin_viewer,
)
from freedom_ls.organisations.factories import OrganisationFactory

LISTED_AND_DETAIL = [
    ("no_owner", True),
    ("owned", True),
    ("shared", True),
    ("held", True),
    ("unreached", False),
]


@pytest.mark.django_db
@pytest.mark.parametrize(("row", "reached"), LISTED_AND_DETAIL)
def test_the_courses_list_holds_a_course_only_when_it_reaches_the_organisation(
    mock_site_context: Site,
    logged_in_client: Callable[[User], Client],
    row: str,
    reached: bool,
) -> None:
    organisation = OrganisationFactory()
    courses = course_per_reach_row(organisation)
    client = logged_in_client(organisation_admin_viewer(organisation))

    response = client.get(_interface_url(organisation.slug, "courses"))

    assert response.status_code == 200
    assert (str(courses[row].pk) in response.content.decode()) is reached


@pytest.mark.django_db
@pytest.mark.parametrize(("row", "reached"), LISTED_AND_DETAIL)
def test_the_course_detail_url_answers_only_for_a_course_that_reaches_the_organisation(
    mock_site_context: Site,
    logged_in_client: Callable[[User], Client],
    row: str,
    reached: bool,
) -> None:
    organisation = OrganisationFactory()
    courses = course_per_reach_row(organisation)
    client = logged_in_client(organisation_admin_viewer(organisation))

    response = client.get(
        _interface_url(organisation.slug, f"courses/{courses[row].pk}")
    )

    assert response.status_code == (200 if reached else 404)


@pytest.mark.usefixtures("_site_context")
@pytest.mark.django_db
def test_a_course_quick_view_404s_since_courses_declare_none(role_holder_client):
    organisation = OrganisationFactory()
    course: Course = CourseFactory()

    response = _get_quick_view(
        role_holder_client(organisation), organisation, f"courses/{course.pk}"
    )

    assert response.status_code == 404
