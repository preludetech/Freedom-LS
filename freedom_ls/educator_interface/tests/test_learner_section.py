"""The educator interface's Learners section.

LearnerConfig lists Learner rows scoped by learners_visible_to. This module
checks the section renders under its name and scoping, and that the
Registered Courses column resolves through its renamed cell template.
"""

from __future__ import annotations

import uuid
from typing import cast

import pytest

from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.educator_interface.views import LearnerDataTable
from freedom_ls.learner_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Cohort, Learner
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.utils import assign_object_role


@pytest.fixture(autouse=True)
def _site_context(mock_site_context):
    """Every test here builds site-aware objects and assigns roles."""


def _make_cohort(*, organisation: Organisation) -> Cohort:
    return cast(
        Cohort, CohortFactory(organisation=organisation, name=f"Cohort {uuid.uuid4()}")
    )


def _make_learner(*, organisation: Organisation, **user_fields: str) -> Learner:
    """A learner in ``organisation``, named by default so the tests can assert
    on what the rendered row says."""
    return cast(
        Learner,
        LearnerFactory(
            user=UserFactory(
                **{"first_name": "Ada", "last_name": "Lovelace", **user_fields}
            ),
            organisation=organisation,
        ),
    )


@pytest.fixture
def educator_client(logged_in_client):
    """Factory: a logged-in staff educator holding ``role`` on ``target`` --
    the organisation for a role holder, a cohort for a grant-only educator."""

    def _make(
        target: Organisation | Cohort, role: str = "organisation_staff"
    ) -> Client:
        educator = UserFactory(staff=True)
        assign_object_role(educator, target, role)
        return cast(Client, logged_in_client(educator))

    return _make


def _learners_url(organisation_slug: str, path_string: str = "learners") -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation_slug, "path_string": path_string},
    )


@pytest.mark.django_db
def test_learners_section_lists_a_learner_visible_to_an_organisation_role_holder(
    educator_client,
):
    organisation = OrganisationFactory()
    _make_learner(organisation=organisation)

    response = educator_client(organisation).get(_learners_url(organisation.slug))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Learners" in content
    assert "Ada" in content


@pytest.mark.django_db
def test_learners_list_excludes_a_learner_from_another_organisation(educator_client):
    """Paired with a learner who should appear: absence alone would also hold
    on a 404, a login redirect or an error page."""
    organisation = OrganisationFactory()
    _make_learner(organisation=organisation)
    _make_learner(
        organisation=OrganisationFactory(), first_name="Grace", last_name="Hopper"
    )

    response = educator_client(organisation).get(_learners_url(organisation.slug))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Ada" in content
    assert "Grace" not in content


@pytest.mark.django_db
def test_learner_detail_page_renders_the_underlying_users_name_and_email(
    educator_client,
):
    organisation = OrganisationFactory()
    learner = _make_learner(organisation=organisation, email="ada@example.com")

    response = educator_client(organisation).get(
        _learners_url(organisation.slug, f"learners/{learner.pk}")
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "Ada" in content
    assert "ada@example.com" in content


@pytest.mark.django_db
def test_learners_list_renders_a_registered_course_through_the_renamed_cell_template(
    educator_client,
):
    organisation = OrganisationFactory()
    LearnerCourseRegistrationFactory(
        learner=_make_learner(organisation=organisation),
        course=CourseFactory(title="Intro to Freedom"),
        is_active=True,
    )

    response = educator_client(organisation).get(_learners_url(organisation.slug))

    assert response.status_code == 200
    assert "Intro to Freedom" in response.content.decode()


@pytest.mark.django_db
def test_cohort_only_educator_cannot_open_a_learner_outside_their_cohort(
    educator_client,
):
    """LearnerConfig.authorise_instance is backed by learners_visible_to, so a
    cohort-scoped educator who can reach the organisation at all still gets a
    404 for a learner outside the cohort they hold a grant on."""
    organisation = OrganisationFactory()
    granted_cohort = _make_cohort(organisation=organisation)
    outside_learner = _make_learner(organisation=organisation)

    response = educator_client(granted_cohort, "instructor").get(
        _learners_url(organisation.slug, f"learners/{outside_learner.pk}")
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_cohort_only_educator_can_open_a_member_of_their_own_cohort(
    educator_client,
):
    organisation = OrganisationFactory()
    granted_cohort = _make_cohort(organisation=organisation)
    member = _make_learner(organisation=organisation)
    CohortMembershipFactory(learner=member, cohort=granted_cohort)

    response = educator_client(granted_cohort, "instructor").get(
        _learners_url(organisation.slug, f"learners/{member.pk}")
    )

    assert response.status_code == 200
    assert "Ada" in response.content.decode()


@pytest.mark.django_db
class TestLearnerDataTableQueryCost:
    """The prefetches in LearnerDataTable.get_queryset are what keep the
    Cohorts and Registered Courses cells' cost from growing with row count."""

    @staticmethod
    def _seed_learners(organisation: Organisation, count: int) -> None:
        """One learner per iteration, each in a cohort of its own and holding a
        registration of its own -- both cells the prefetches feed."""
        for _ in range(count):
            learner = LearnerFactory(user=UserFactory(), organisation=organisation)
            CohortMembershipFactory(
                learner=learner, cohort=_make_cohort(organisation=organisation)
            )
            LearnerCourseRegistrationFactory(
                learner=learner, course=CourseFactory(), is_active=True
            )

    def _render_query_count(self, site_aware_request, learner_count: int) -> int:
        organisation = OrganisationFactory()
        educator = UserFactory(staff=True)
        assign_object_role(educator, organisation, "organisation_staff")
        self._seed_learners(organisation, learner_count)

        request = site_aware_request.get("/")
        request.user = educator
        request.organisation = organisation
        request.panel_url_kwargs = {"organisation_slug": organisation.slug}

        with CaptureQueriesContext(connection) as captured:
            LearnerDataTable.render(request)
        return len(captured.captured_queries)

    def test_query_count_does_not_grow_with_learner_count(self, site_aware_request):
        """Compares the two row counts rather than bounding both by a ceiling:
        a ceiling with any slack in it lets one extra query per row hide under
        the bound, which is the only thing this test exists to catch."""
        one_learner = self._render_query_count(site_aware_request, learner_count=1)
        four_learners = self._render_query_count(site_aware_request, learner_count=4)

        assert one_learner == four_learners
