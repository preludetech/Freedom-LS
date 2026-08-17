"""The organisation switcher: switching organisation via the X-Organisation-
Switch header, the narrow OrganisationScopeDenied catch, and the switcher /
announcer OOB fragments a switch response carries.

Structural precedent: test_organisation_isolation.py sets up the same two-
organisation shape; this module drives the switch header instead of plain
navigation.
"""

from __future__ import annotations

import lxml.html
import pytest

from django.contrib.messages import get_messages
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role
from freedom_ls.student_management.factories import CohortFactory


@pytest.fixture(autouse=True)
def _site_context(mock_site_context):
    """Every test here builds site-aware objects and assigns roles."""


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


def _switcher(response) -> str:
    """The rendered #organisation-switcher element.

    Selected from the parsed document rather than sliced out of the raw
    response, so the assertions do not depend on what happens to render
    after the switcher.
    """
    document = lxml.html.fromstring(response.content)
    elements = document.cssselect("#organisation-switcher")
    assert elements, "no #organisation-switcher in the response"
    return str(lxml.html.tostring(elements[0], encoding="unicode"))


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

        # That the announcement rides an out-of-band swap into the persistent
        # live region is panel_framework's contract, asserted in its own
        # test_htmx_navigation. What is host-specific is the wording.
        assert "Now viewing Org B" in response.content.decode()

    def test_switch_response_carries_the_updated_switcher_label(self, logged_in_client):
        _organisation_a, organisation_b, _cohort_a, educator = (
            _two_organisation_educator()
        )
        client = logged_in_client(educator)

        response = _switch(client, _interface_url(organisation_b.slug, "cohorts"))

        assert "Org B" in _switcher(response)

    def test_switcher_links_keep_the_visitor_on_the_same_section(
        self, logged_in_client
    ):
        """Switching from the users list must land on the other organisation's
        users list, not bounce the visitor back to cohorts."""
        organisation_a, organisation_b, _cohort_a, educator = (
            _two_organisation_educator()
        )
        client = logged_in_client(educator)

        response = client.get(_interface_url(organisation_a.slug, "users"))

        assert _interface_url(organisation_b.slug, "users") in _switcher(response)


@pytest.mark.django_db
class TestSwitchOnAForeignDetailPage:
    """Switching while sitting on a detail page belonging to the organisation
    being left: the detail row does not exist in the new organisation, so the
    switch softens to that organisation's list rather than 404ing."""

    @pytest.fixture
    def switch_response(self, logged_in_client):
        _organisation_a, organisation_b, cohort_a, educator = (
            _two_organisation_educator()
        )
        CohortFactory(organisation=organisation_b, name="Cohort B Only")
        client = logged_in_client(educator)

        response = _switch(
            client, _interface_url(organisation_b.slug, f"cohorts/{cohort_a.pk}")
        )
        response.organisation_b = organisation_b
        return response

    def test_returns_the_new_organisations_list_instead_of_a_404(self, switch_response):
        assert switch_response.status_code == 200
        content = switch_response.content.decode()
        assert "Cohort B Only" in content
        assert "Cohort A Only" not in content

    def test_sets_hx_push_url_to_the_list(self, switch_response):
        assert switch_response["HX-Push-Url"] == _interface_url(
            switch_response.organisation_b.slug, "cohorts"
        )

    def test_queues_an_info_message_naming_the_new_organisation(self, switch_response):
        messages = [str(m) for m in get_messages(switch_response.wsgi_request)]

        assert messages == [
            "Switched to Org B — that cohort isn't in this organisation"
        ]

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

        switcher = _switcher(response)
        assert "Solo Org" in switcher
        assert 'role="menuitemradio"' not in switcher

    def test_two_accessible_organisations_renders_current_one_as_checked(
        self, logged_in_client
    ):
        organisation_a, _organisation_b, _cohort_a, educator = (
            _two_organisation_educator()
        )
        client = logged_in_client(educator)

        response = client.get(_interface_url(organisation_a.slug, "cohorts"))

        switcher = _switcher(response)
        assert 'role="menuitemradio"' in switcher
        assert 'aria-checked="true"' in switcher
        assert 'aria-checked="false"' in switcher
