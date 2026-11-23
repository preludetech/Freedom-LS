"""The cohort quick view: educator_interface/panels/cohort/quick_view.py."""

from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.educator_interface.tests.helpers import (
    RoleHolderClient,
    _get_quick_view,
    _quick_view_url,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.organisations.factories import OrganisationFactory

# Every test here builds site-aware objects and assigns roles.
pytestmark = pytest.mark.usefixtures("mock_site_context")


@pytest.mark.django_db
class TestCohortQuickView:
    def test_shows_the_cohorts_name(self, role_holder_client: RoleHolderClient) -> None:
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation, name="Year 9 Maths")

        response = _get_quick_view(
            role_holder_client(organisation), organisation, f"cohorts/{cohort.pk}"
        )

        assert response.status_code == 200
        assert "Year 9 Maths" in response.content.decode()

    def test_shows_the_learner_count(
        self, role_holder_client: RoleHolderClient
    ) -> None:
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)
        CohortMembershipFactory(
            cohort=cohort, learner=LearnerFactory(organisation=organisation)
        )
        CohortMembershipFactory(
            cohort=cohort, learner=LearnerFactory(organisation=organisation)
        )

        response = _get_quick_view(
            role_holder_client(organisation), organisation, f"cohorts/{cohort.pk}"
        )

        assert "2" in response.content.decode()

    def test_reads_active_from_an_active_cohort(
        self, role_holder_client: RoleHolderClient
    ) -> None:
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)

        response = _get_quick_view(
            role_holder_client(organisation), organisation, f"cohorts/{cohort.pk}"
        )

        assert "Inactive" not in response.content.decode()
        assert "Active" in response.content.decode()

    def test_reads_inactive_from_an_inactive_cohort(
        self, role_holder_client: RoleHolderClient
    ) -> None:
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation, is_active=False)

        response = _get_quick_view(
            role_holder_client(organisation), organisation, f"cohorts/{cohort.pk}"
        )

        assert "Inactive" in response.content.decode()

    def test_lists_its_registered_courses(
        self, role_holder_client: RoleHolderClient
    ) -> None:
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)
        CohortCourseRegistrationFactory(
            cohort=cohort, course=CourseFactory(title="Intro to Freedom")
        )

        response = _get_quick_view(
            role_holder_client(organisation), organisation, f"cohorts/{cohort.pk}"
        )

        assert "Intro to Freedom" in response.content.decode()

    def test_a_cohort_in_another_organisation_404s(
        self, role_holder_client: RoleHolderClient
    ) -> None:
        organisation = OrganisationFactory()
        outside_cohort = CohortFactory(organisation=OrganisationFactory())

        response = _get_quick_view(
            role_holder_client(organisation),
            organisation,
            f"cohorts/{outside_cohort.pk}",
        )

        assert response.status_code == 404

    def test_a_non_htmx_get_redirects_to_the_instance_page(
        self, role_holder_client: RoleHolderClient
    ) -> None:
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)

        response = role_holder_client(organisation).get(
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

    def test_response_varies_on_hx_request(
        self, role_holder_client: RoleHolderClient
    ) -> None:
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)

        response = _get_quick_view(
            role_holder_client(organisation), organisation, f"cohorts/{cohort.pk}"
        )

        assert "HX-Request" in response["Vary"]


@pytest.mark.django_db
def test_the_cohorts_list_renders_the_quick_view_trigger_attributes(
    role_holder_client: RoleHolderClient,
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Year 9 Maths")

    response = role_holder_client(organisation).get(
        reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation.slug, "path_string": "cohorts"},
        )
    )

    content = response.content.decode()
    expected_url = _quick_view_url(organisation.slug, f"cohorts/{cohort.pk}")
    assert f'hx-get="{expected_url}"' in content
    assert 'aria-controls="quick-view"' in content
