"""The cohort and staff quick views: educator_interface/quick_views.py.

An htmx GET of `<section>/<pk>/__quick-view` returns the drawer's frame with
each consumer's own fields, scoped the same way the section's own list and
instance pages are.
"""

from __future__ import annotations

import pytest

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.tests.helpers import _get_quick_view
from freedom_ls.organisations.factories import OrganisationFactory


@pytest.fixture(autouse=True)
def _site_context(mock_site_context):
    """Every test here builds site-aware objects and assigns roles."""


@pytest.mark.django_db
def test_a_course_quick_view_404s_since_courses_declare_none(role_holder_client):
    organisation = OrganisationFactory()
    course: Course = CourseFactory()

    response = _get_quick_view(
        role_holder_client(organisation), organisation, f"courses/{course.pk}"
    )

    assert response.status_code == 404
