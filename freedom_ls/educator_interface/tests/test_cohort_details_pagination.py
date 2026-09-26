"""A cohort's Details tab holds two tables side by side: its course
registrations and its learners. Each paginates through its own table key, so
paging one leaves the other on its own page."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from django.contrib.sites.models import Site
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Cohort
from freedom_ls.organisations.factories import OrganisationFactory


def _cohort_url(cohort: Cohort) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": cohort.organisation.slug,
            "path_string": f"cohorts/{cohort.pk}",
        },
    )


@pytest.mark.django_db
def test_learners_page_param_leaves_course_registrations_on_page_one(
    mock_site_context: Site, logged_in_client: Callable[[User], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Big Cohort")
    for i in range(26):
        learner = LearnerFactory(
            user=UserFactory(first_name=f"Learner{i:02d}", last_name="Test"),
            organisation=organisation,
        )
        CohortMembershipFactory(cohort=cohort, learner=learner)
    for i in range(2):
        CohortCourseRegistrationFactory(
            cohort=cohort, course=CourseFactory(title=f"Course {i}")
        )
    client = logged_in_client(UserFactory(superuser=True))

    response = client.get(_cohort_url(cohort), {"learners-page": "2"})

    assert response.status_code == 200
    content = response.content.decode()
    # The learners table is on its own page 2: the 26th learner shows, the
    # 1st (on page 1) does not.
    assert "Learner25" in content
    assert "Learner00" not in content
    # The course registrations table is untouched, still on page 1.
    assert "Course 0" in content
    assert "Course 1" in content
