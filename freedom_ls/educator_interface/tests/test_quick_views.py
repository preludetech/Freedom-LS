"""The learner and cohort quick views: educator_interface/quick_views.py.

LearnerConfig and CohortConfig now declare a `quick_view`, so an htmx GET of
`<section>/<pk>/__quick-view` returns the drawer's frame with each consumer's
own fields, scoped the same way the section's own list and instance pages
already are.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from django.test import Client
from django.urls import reverse

if TYPE_CHECKING:
    # Stub-only: the test client's response carries `templates`, which a plain
    # HttpResponse does not.
    from django.test.client import _MonkeyPatchedWSGIResponse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Cohort, Learner
from freedom_ls.learner_progress.utils import ensure_course_progress_record
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.role_based_permissions.utils import assign_object_role


@pytest.fixture(autouse=True)
def _site_context(mock_site_context):
    """Every test here builds site-aware objects and assigns roles."""


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


def _quick_view_url(organisation_slug: str, path_string: str) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": organisation_slug,
            "path_string": f"{path_string}/__quick-view",
        },
    )


def _get_quick_view(
    client: Client, organisation: Organisation, path_string: str
) -> _MonkeyPatchedWSGIResponse:
    return client.get(
        _quick_view_url(organisation.slug, path_string), HTTP_HX_REQUEST="true"
    )


@pytest.mark.django_db
class TestLearnerQuickView:
    def test_shows_the_learners_name_and_email(self, educator_client):
        organisation = OrganisationFactory()
        learner = cast(
            Learner,
            LearnerFactory(
                user=UserFactory(
                    first_name="Ada", last_name="Lovelace", email="ada@example.com"
                ),
                organisation=organisation,
            ),
        )

        response = _get_quick_view(
            educator_client(organisation), organisation, f"learners/{learner.pk}"
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert "Ada Lovelace" in content
        assert "ada@example.com" in content

    def test_shows_active_status_for_an_active_learner(self, educator_client):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation, is_active=True)

        response = _get_quick_view(
            educator_client(organisation), organisation, f"learners/{learner.pk}"
        )

        assert "Active" in response.content.decode()

    def test_lists_a_visible_cohort_membership_as_a_link(self, educator_client):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)
        cohort = CohortFactory(organisation=organisation, name="Year 9 Maths")
        CohortMembershipFactory(learner=learner, cohort=cohort)

        response = _get_quick_view(
            educator_client(organisation), organisation, f"learners/{learner.pk}"
        )

        content = response.content.decode()
        assert "Year 9 Maths" in content
        assert f"cohorts/{cohort.pk}" in content

    def test_shows_a_course_registration_through_a_cohort_with_its_progress(
        self, educator_client
    ):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)
        cohort = CohortFactory(organisation=organisation, name="Year 9 Maths")
        CohortMembershipFactory(learner=learner, cohort=cohort)
        course: Course = CourseFactory(title="Intro to Freedom")
        registration = CohortCourseRegistrationFactory(cohort=cohort, course=course)
        record = ensure_course_progress_record(learner, course, registration)
        record.progress_percentage = 55
        record.save(update_fields=["progress_percentage"])

        response = _get_quick_view(
            educator_client(organisation), organisation, f"learners/{learner.pk}"
        )

        content = response.content.decode()
        assert "Intro to Freedom" in content
        assert "Year 9 Maths" in content
        assert "55" in content

    def test_shows_no_progress_yet_for_a_registration_with_no_record(
        self, educator_client
    ):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)
        LearnerCourseRegistrationFactory(
            learner=learner, course=CourseFactory(title="Untouched Course")
        )

        response = _get_quick_view(
            educator_client(organisation), organisation, f"learners/{learner.pk}"
        )

        content = response.content.decode()
        assert "Untouched Course" in content
        assert "No progress yet" in content

    def test_shows_never_for_a_learner_with_no_progress_records(self, educator_client):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)

        response = _get_quick_view(
            educator_client(organisation), organisation, f"learners/{learner.pk}"
        )

        assert "Never" in response.content.decode()

    def test_a_learner_in_another_organisation_404s(self, educator_client):
        organisation = OrganisationFactory()
        outside_learner = LearnerFactory(organisation=OrganisationFactory())

        response = _get_quick_view(
            educator_client(organisation),
            organisation,
            f"learners/{outside_learner.pk}",
        )

        assert response.status_code == 404

    def test_a_malformed_pk_404s(self, educator_client):
        organisation = OrganisationFactory()

        response = _get_quick_view(
            educator_client(organisation), organisation, "learners/not-a-uuid"
        )

        assert response.status_code == 404

    def test_a_non_htmx_get_redirects_to_the_instance_page(self, educator_client):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)

        response = educator_client(organisation).get(
            _quick_view_url(organisation.slug, f"learners/{learner.pk}")
        )

        assert response.status_code == 302
        assert response["Location"] == reverse(
            "educator_interface:interface",
            kwargs={
                "organisation_slug": organisation.slug,
                "path_string": f"learners/{learner.pk}",
            },
        )

    def test_response_varies_on_hx_request(self, educator_client):
        organisation = OrganisationFactory()
        learner = LearnerFactory(organisation=organisation)

        response = _get_quick_view(
            educator_client(organisation), organisation, f"learners/{learner.pk}"
        )

        assert "HX-Request" in response["Vary"]

    def test_an_instructor_scoped_to_one_cohort_does_not_see_a_membership_elsewhere(
        self, educator_client
    ):
        organisation = OrganisationFactory()
        granted_cohort = CohortFactory(organisation=organisation, name="Granted")
        other_cohort = CohortFactory(organisation=organisation, name="Elsewhere")
        learner = LearnerFactory(organisation=organisation)
        CohortMembershipFactory(learner=learner, cohort=granted_cohort)
        CohortMembershipFactory(learner=learner, cohort=other_cohort)

        response = _get_quick_view(
            educator_client(granted_cohort, "instructor"),
            organisation,
            f"learners/{learner.pk}",
        )

        content = response.content.decode()
        assert "Granted" in content
        assert "Elsewhere" not in content


@pytest.mark.django_db
class TestCohortQuickView:
    def test_shows_the_cohorts_name(self, educator_client):
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation, name="Year 9 Maths")

        response = _get_quick_view(
            educator_client(organisation), organisation, f"cohorts/{cohort.pk}"
        )

        assert response.status_code == 200
        assert "Year 9 Maths" in response.content.decode()

    def test_shows_the_learner_count(self, educator_client):
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)
        CohortMembershipFactory(
            cohort=cohort, learner=LearnerFactory(organisation=organisation)
        )
        CohortMembershipFactory(
            cohort=cohort, learner=LearnerFactory(organisation=organisation)
        )

        response = _get_quick_view(
            educator_client(organisation), organisation, f"cohorts/{cohort.pk}"
        )

        assert "2" in response.content.decode()

    def test_lists_its_registered_courses(self, educator_client):
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)
        CohortCourseRegistrationFactory(
            cohort=cohort, course=CourseFactory(title="Intro to Freedom")
        )

        response = _get_quick_view(
            educator_client(organisation), organisation, f"cohorts/{cohort.pk}"
        )

        assert "Intro to Freedom" in response.content.decode()

    def test_a_cohort_in_another_organisation_404s(self, educator_client):
        organisation = OrganisationFactory()
        outside_cohort = CohortFactory(organisation=OrganisationFactory())

        response = _get_quick_view(
            educator_client(organisation), organisation, f"cohorts/{outside_cohort.pk}"
        )

        assert response.status_code == 404

    def test_a_non_htmx_get_redirects_to_the_instance_page(self, educator_client):
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)

        response = educator_client(organisation).get(
            _quick_view_url(organisation.slug, f"cohorts/{cohort.pk}")
        )

        assert response.status_code == 302
        assert response["Location"] == reverse(
            "educator_interface:interface",
            kwargs={
                "organisation_slug": organisation.slug,
                "path_string": f"cohorts/{cohort.pk}",
            },
        )

    def test_response_varies_on_hx_request(self, educator_client):
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)

        response = _get_quick_view(
            educator_client(organisation), organisation, f"cohorts/{cohort.pk}"
        )

        assert "HX-Request" in response["Vary"]


@pytest.mark.django_db
def test_a_course_quick_view_404s_since_courses_declare_none(educator_client):
    organisation = OrganisationFactory()
    course: Course = CourseFactory()

    response = _get_quick_view(
        educator_client(organisation), organisation, f"courses/{course.pk}"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_the_learners_list_renders_the_quick_view_trigger_attributes(
    educator_client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(
        organisation=organisation, user=UserFactory(first_name="Ada")
    )

    response = educator_client(organisation).get(
        reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation.slug, "path_string": "learners"},
        )
    )

    content = response.content.decode()
    expected_url = _quick_view_url(organisation.slug, f"learners/{learner.pk}")
    assert f'hx-get="{expected_url}"' in content
    assert 'aria-controls="quick-view"' in content


@pytest.mark.django_db
def test_the_cohorts_list_renders_the_quick_view_trigger_attributes(
    educator_client,
):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Year 9 Maths")

    response = educator_client(organisation).get(
        reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation.slug, "path_string": "cohorts"},
        )
    )

    content = response.content.decode()
    expected_url = _quick_view_url(organisation.slug, f"cohorts/{cohort.pk}")
    assert f'hx-get="{expected_url}"' in content
    assert 'aria-controls="quick-view"' in content
