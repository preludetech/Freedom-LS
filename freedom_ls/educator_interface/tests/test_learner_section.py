"""The educator interface's Learners section.

LearnerConfig lists Learner rows scoped by learners_visible_to. This module
checks the section renders under its name and scoping, and that the
Registered Courses column resolves through its renamed cell template.
"""

from __future__ import annotations

import uuid
from typing import cast

import pytest

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
from freedom_ls.learner_management.models import Cohort
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


def _learners_url(organisation_slug: str, path_string: str = "learners") -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation_slug, "path_string": path_string},
    )


@pytest.mark.django_db
def test_learners_section_lists_a_learner_visible_to_an_organisation_role_holder(
    logged_in_client,
):
    organisation = OrganisationFactory()
    LearnerFactory(
        user=UserFactory(first_name="Ada", last_name="Lovelace"),
        organisation=organisation,
    )
    educator = UserFactory(staff=True)
    assign_object_role(educator, organisation, "organisation_staff")
    client = logged_in_client(educator)

    response = client.get(_learners_url(organisation.slug))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Learners" in content
    assert "Ada" in content


@pytest.mark.django_db
def test_learners_list_excludes_a_learner_from_another_organisation(logged_in_client):
    organisation = OrganisationFactory()
    LearnerFactory(
        user=UserFactory(first_name="Grace", last_name="Hopper"),
        organisation=OrganisationFactory(),
    )
    educator = UserFactory(staff=True)
    assign_object_role(educator, organisation, "organisation_staff")
    client = logged_in_client(educator)

    response = client.get(_learners_url(organisation.slug))

    assert "Grace" not in response.content.decode()


@pytest.mark.django_db
def test_learner_detail_page_renders_the_underlying_users_name_and_email(
    logged_in_client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(
        user=UserFactory(
            first_name="Ada", last_name="Lovelace", email="ada@example.com"
        ),
        organisation=organisation,
    )
    educator = UserFactory(staff=True)
    assign_object_role(educator, organisation, "organisation_staff")
    client = logged_in_client(educator)

    response = client.get(_learners_url(organisation.slug, f"learners/{learner.pk}"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Ada" in content
    assert "ada@example.com" in content


@pytest.mark.django_db
def test_learners_list_renders_a_registered_course_through_the_renamed_cell_template(
    logged_in_client,
):
    organisation = OrganisationFactory()
    course = CourseFactory(title="Intro to Freedom")
    learner = LearnerFactory(
        user=UserFactory(first_name="Ada", last_name="Lovelace"),
        organisation=organisation,
    )
    LearnerCourseRegistrationFactory(learner=learner, collection=course, is_active=True)
    educator = UserFactory(staff=True)
    assign_object_role(educator, organisation, "organisation_staff")
    client = logged_in_client(educator)

    response = client.get(_learners_url(organisation.slug))

    assert response.status_code == 200
    assert "Intro to Freedom" in response.content.decode()


@pytest.mark.django_db
def test_cohort_only_educator_cannot_open_a_learner_outside_their_cohort(
    logged_in_client,
):
    """LearnerConfig.authorise_instance is backed by learners_visible_to, so a
    cohort-scoped educator who can reach the organisation at all still gets a
    404 for a learner outside the cohort they hold a grant on."""
    organisation = OrganisationFactory()
    granted_cohort = _make_cohort(organisation=organisation)
    outside_learner = LearnerFactory(user=UserFactory(), organisation=organisation)
    educator = UserFactory(staff=True)
    assign_object_role(educator, granted_cohort, "instructor")
    client = logged_in_client(educator)

    response = client.get(
        _learners_url(organisation.slug, f"learners/{outside_learner.pk}")
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_cohort_only_educator_can_open_a_member_of_their_own_cohort(
    logged_in_client,
):
    organisation = OrganisationFactory()
    granted_cohort = _make_cohort(organisation=organisation)
    member = LearnerFactory(
        user=UserFactory(first_name="Ada", last_name="Lovelace"),
        organisation=organisation,
    )
    CohortMembershipFactory(learner=member, cohort=granted_cohort)
    educator = UserFactory(staff=True)
    assign_object_role(educator, granted_cohort, "instructor")
    client = logged_in_client(educator)

    response = client.get(_learners_url(organisation.slug, f"learners/{member.pk}"))

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
                learner=learner, collection=CourseFactory(), is_active=True
            )

    @pytest.mark.parametrize("learner_count", [1, 4])
    def test_query_count_does_not_grow_with_learner_count(
        self,
        mock_site_context,
        site_aware_request,
        django_assert_max_num_queries,
        learner_count,
    ):
        organisation = OrganisationFactory()
        educator = UserFactory(staff=True)
        assign_object_role(educator, organisation, "organisation_staff")

        self._seed_learners(organisation, learner_count)

        request = site_aware_request.get("/")
        request.user = educator
        request.organisation = organisation
        request.panel_url_kwargs = {"organisation_slug": organisation.slug}

        with django_assert_max_num_queries(11):
            LearnerDataTable.render(request)
