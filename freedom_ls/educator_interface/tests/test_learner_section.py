"""The educator interface's Learners section.

LearnerConfig lists Learner rows scoped by learners_visible_to. This module
checks the section renders under its name and scoping, and that the
Registered Courses column resolves through its renamed cell template.
"""

from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.learner_management.models import (
    Cohort,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role


@pytest.fixture(autouse=True)
def _site_context(mock_site_context):
    """Every test here builds site-aware objects and assigns roles."""


# Direct-creation stopgap for Learner-based enrolment models:
# learner_management.factories still imports the pre-rename model names and
# is rewritten in a later batch, so its factories cannot be used here yet.


def _make_learner(user, *, organisation, is_active: bool = True) -> Learner:
    return Learner.objects.create(
        user=user, organisation=organisation, is_active=is_active
    )


def _make_cohort(*, organisation) -> Cohort:
    return Cohort.objects.create(organisation=organisation, name="Cohort")


def _learners_url(organisation_slug: str, path_string: str = "learners") -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation_slug, "path_string": path_string},
    )


@pytest.mark.django_db
def test_learners_list_names_the_section_learners_not_users(logged_in_client):
    organisation = OrganisationFactory()
    _make_learner(
        UserFactory(first_name="Ada", last_name="Lovelace"), organisation=organisation
    )
    educator = UserFactory(staff=True)
    assign_object_role(educator, organisation, "organisation_staff")
    client = logged_in_client(educator)

    response = client.get(_learners_url(organisation.slug))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Learners" in content
    assert "Users" not in content


@pytest.mark.django_db
def test_learners_list_shows_a_learner_visible_to_an_organisation_role_holder(
    logged_in_client,
):
    organisation = OrganisationFactory()
    _make_learner(
        UserFactory(first_name="Ada", last_name="Lovelace"), organisation=organisation
    )
    educator = UserFactory(staff=True)
    assign_object_role(educator, organisation, "organisation_staff")
    client = logged_in_client(educator)

    response = client.get(_learners_url(organisation.slug))

    assert "Ada" in response.content.decode()


@pytest.mark.django_db
def test_learners_list_excludes_a_learner_from_another_organisation(logged_in_client):
    organisation = OrganisationFactory()
    _make_learner(
        UserFactory(first_name="Grace", last_name="Hopper"),
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
    learner = _make_learner(
        UserFactory(first_name="Ada", last_name="Lovelace", email="ada@example.com"),
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
    learner = _make_learner(
        UserFactory(first_name="Ada", last_name="Lovelace"), organisation=organisation
    )
    LearnerCourseRegistration.objects.create(
        learner=learner, collection=course, is_active=True
    )
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
    outside_learner = _make_learner(UserFactory(), organisation=organisation)
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
    member = _make_learner(
        UserFactory(first_name="Ada", last_name="Lovelace"), organisation=organisation
    )
    CohortMembership.objects.create(learner=member, cohort=granted_cohort)
    educator = UserFactory(staff=True)
    assign_object_role(educator, granted_cohort, "instructor")
    client = logged_in_client(educator)

    response = client.get(_learners_url(organisation.slug, f"learners/{member.pk}"))

    assert response.status_code == 200
    assert "Ada" in response.content.decode()
