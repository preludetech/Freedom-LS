"""Shared helpers for tests that read an educator page as an organisation admin."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import lxml.html
from pytest_django.fixtures import DjangoAssertNumQueries

from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course, CourseAudience
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.utils import assign_object_role


def organisation_admin_viewer(organisation: Organisation) -> User:
    viewer = cast(User, UserFactory(staff=True))
    assign_object_role(viewer, organisation, "organisation_admin")
    return viewer


def get_interface_page(
    organisation: Organisation, path_string: str, viewer: User
) -> str:
    client = Client()
    client.force_login(viewer)
    response = client.get(
        reverse(
            "educator_interface:interface",
            kwargs={
                "organisation_slug": organisation.slug,
                "path_string": path_string,
            },
        )
    )
    assert response.status_code == 200
    return str(response.content.decode())


def profile_picture_sources(content: str) -> list[str]:
    return [
        image.get("src")
        for image in lxml.html.fromstring(content).cssselect(
            "img[data-profile-picture]"
        )
    ]


def page_after_adding_rows(
    organisation: Organisation,
    path_string: str,
    add_rows: Callable[[Organisation, int], None],
    django_assert_max_num_queries: DjangoAssertNumQueries,
) -> str:
    """The page once four more rows are added, asserting it costs no more queries than with one."""
    viewer = organisation_admin_viewer(organisation)
    add_rows(organisation, 1)
    with CaptureQueriesContext(connection) as one_row:
        get_interface_page(organisation, path_string, viewer)
    add_rows(organisation, 4)

    with django_assert_max_num_queries(len(one_row.captured_queries)):
        return get_interface_page(organisation, path_string, viewer)


def _public_course() -> Course:
    return cast(Course, CourseFactory(audience=CourseAudience.PUBLIC))


def course_per_reach_row(organisation: Organisation) -> dict[str, Course]:
    """One public, published course for each way a course can stand to
    `organisation`, keyed by row id:

    - ``no_owner``: no owning organisation.
    - ``owned``: owned by `organisation`.
    - ``shared``: owned by another organisation and shared with `organisation`.
    - ``held``: owned by another organisation, not shared, but a cohort and a
      learner of `organisation` each hold an inactive registration on it.
    - ``unreached``: owned by another organisation, not shared, with no
      registration held by `organisation`.
    """
    other = OrganisationFactory()
    owned = _public_course()
    owned.organisations.add(organisation)
    shared = _public_course()
    shared.organisations.add(other)
    shared.shared_with.add(organisation)
    held = _public_course()
    held.organisations.add(other)
    CohortCourseRegistrationFactory(
        cohort=CohortFactory(organisation=organisation), course=held, is_active=False
    )
    LearnerCourseRegistrationFactory(
        learner=LearnerFactory(organisation=organisation), course=held, is_active=False
    )
    unreached = _public_course()
    unreached.organisations.add(other)
    return {
        "no_owner": _public_course(),
        "owned": owned,
        "shared": shared,
        "held": held,
        "unreached": unreached,
    }
