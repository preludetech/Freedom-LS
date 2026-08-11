"""The organisation switcher: switching organisation via the X-Organisation-
Switch header, the narrow OrganisationScopeDenied catch, and the switcher /
announcer OOB fragments a switch response carries.

Structural precedent: test_organisation_isolation.py sets up the same two-
organisation shape; this module drives the switch header instead of plain
navigation.
"""

from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role
from freedom_ls.student_management.factories import CohortFactory


@pytest.fixture(autouse=True)
def _mock_get_current_site(mock_site_context, mocker):
    """assign_object_role resolves the current site via Site.objects.get_current(),
    a separate lookup from the thread-local mock_site_context sets up for the
    ORM. Point both at the same site so role assignment works here."""
    mocker.patch(
        "django.contrib.sites.models.SiteManager.get_current",
        return_value=mock_site_context,
    )


def _interface_url(organisation_slug: str, path_string: str) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation_slug, "path_string": path_string},
    )


def _switch(client, url: str):
    return client.get(
        url,
        HTTP_HX_REQUEST="true",
        HTTP_HX_TARGET="main-content",
        HTTP_X_ORGANISATION_SWITCH="true",
    )


def _two_organisation_educator():
    """An educator with organisation_staff on two organisations, plus a
    cohort that lives only in the first."""
    organisation_a = OrganisationFactory(name="Org A")
    organisation_b = OrganisationFactory(name="Org B")
    cohort_a = CohortFactory(organisation=organisation_a, name="Cohort A Only")
    educator = UserFactory(staff=True)
    assign_object_role(educator, organisation_a, "organisation_staff")
    assign_object_role(educator, organisation_b, "organisation_staff")
    return organisation_a, organisation_b, cohort_a, educator


@pytest.mark.django_db
class TestSwitchOnAListPage:
    def test_switching_to_another_organisations_list_shows_its_content(
        self, logged_in_client
    ):
        _organisation_a, organisation_b, _cohort_a, educator = (
            _two_organisation_educator()
        )
        CohortFactory(organisation=organisation_b, name="Cohort B Only")
        client = logged_in_client(educator)

        response = _switch(client, _interface_url(organisation_b.slug, "cohorts"))

        assert response.status_code == 200
        assert b"Cohort B Only" in response.content

    def test_switch_response_carries_the_live_region_announcement(
        self, logged_in_client
    ):
        _organisation_a, organisation_b, _cohort_a, educator = (
            _two_organisation_educator()
        )
        client = logged_in_client(educator)

        response = _switch(client, _interface_url(organisation_b.slug, "cohorts"))

        content = response.content.decode()
        assert 'hx-swap-oob="innerHTML:#scope-announcer"' in content
        assert 'id="scope-announcer"' not in content
        assert "Now viewing Org B" in content

    def test_switch_response_carries_the_updated_switcher_label(self, logged_in_client):
        _organisation_a, organisation_b, _cohort_a, educator = (
            _two_organisation_educator()
        )
        client = logged_in_client(educator)

        response = _switch(client, _interface_url(organisation_b.slug, "cohorts"))

        content = response.content.decode()
        switcher_fragment = content[content.index('id="organisation-switcher"') :]
        assert "Org B" in switcher_fragment


@pytest.mark.django_db
class TestSwitchOnAForeignDetailPage:
    def test_returns_the_list_content_instead_of_a_404(self, logged_in_client):
        _organisation_a, organisation_b, cohort_a, educator = (
            _two_organisation_educator()
        )
        client = logged_in_client(educator)

        response = _switch(
            client, _interface_url(organisation_b.slug, f"cohorts/{cohort_a.pk}")
        )

        assert response.status_code == 200
        assert b"Cohort A Only" not in response.content

    def test_sets_hx_push_url_to_the_list(self, logged_in_client):
        _organisation_a, organisation_b, cohort_a, educator = (
            _two_organisation_educator()
        )
        client = logged_in_client(educator)

        response = _switch(
            client, _interface_url(organisation_b.slug, f"cohorts/{cohort_a.pk}")
        )

        assert response["HX-Push-Url"] == _interface_url(organisation_b.slug, "cohorts")

    def test_queues_an_info_message_naming_the_new_organisation(self, logged_in_client):
        _organisation_a, organisation_b, cohort_a, educator = (
            _two_organisation_educator()
        )
        client = logged_in_client(educator)

        response = _switch(
            client, _interface_url(organisation_b.slug, f"cohorts/{cohort_a.pk}")
        )

        content = response.content.decode()
        assert "Switched to Org B" in content
        assert "in this organisation" in content

    def test_foreign_detail_without_the_switch_header_still_404s(
        self, logged_in_client
    ):
        _organisation_a, organisation_b, cohort_a, educator = (
            _two_organisation_educator()
        )
        client = logged_in_client(educator)

        response = client.get(
            _interface_url(organisation_b.slug, f"cohorts/{cohort_a.pk}"),
            HTTP_HX_REQUEST="true",
            HTTP_HX_TARGET="main-content",
        )

        assert response.status_code == 404

    def test_switch_to_a_genuinely_nonexistent_path_segment_still_404s(
        self, logged_in_client
    ):
        """Pins the narrow OrganisationScopeDenied catch: an unknown path
        segment is a different failure than "wrong organisation" and must
        not be relabelled into the softened redirect, switch header or not.
        """
        _organisation_a, organisation_b, _cohort_a, educator = (
            _two_organisation_educator()
        )
        client = logged_in_client(educator)

        response = _switch(
            client, _interface_url(organisation_b.slug, "no-such-section")
        )

        assert response.status_code == 404


@pytest.mark.django_db
class TestSwitcherRendering:
    def test_single_accessible_organisation_renders_static_text_not_a_dropdown(
        self, logged_in_client
    ):
        organisation = OrganisationFactory(name="Solo Org")
        educator = UserFactory(staff=True)
        assign_object_role(educator, organisation, "organisation_staff")
        client = logged_in_client(educator)

        response = client.get(_interface_url(organisation.slug, "cohorts"))

        content = response.content.decode()
        switcher_fragment = content[
            content.index('id="organisation-switcher"') : content.index(
                'id="sidebar-nav"'
            )
        ]
        assert "Solo Org" in switcher_fragment
        assert "aria-haspopup" not in switcher_fragment

    def test_two_accessible_organisations_renders_current_one_as_checked(
        self, logged_in_client
    ):
        organisation_a, _organisation_b, _cohort_a, educator = (
            _two_organisation_educator()
        )
        client = logged_in_client(educator)

        response = client.get(_interface_url(organisation_a.slug, "cohorts"))

        content = response.content.decode()
        switcher_fragment = content[
            content.index('id="organisation-switcher"') : content.index(
                'id="sidebar-nav"'
            )
        ]
        assert 'role="menuitemradio"' in switcher_fragment
        assert 'aria-checked="true"' in switcher_fragment
        assert 'aria-checked="false"' in switcher_fragment
