"""Tests for the educator interface URL shape: the bare-root redirect
(interface_root), resolving and authorising an organisation once
(interface), and that every reverse()/{% url %} call the F4 sweep touched
still resolves.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from django.contrib.sessions.backends.db import SessionStore
from django.http import Http404
from django.test import RequestFactory
from django.urls import NoReverseMatch, reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.educator_interface.views import (
    LAST_ORGANISATION_SESSION_KEY,
    interface,
    interface_root,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role
from freedom_ls.student_management.factories import CohortFactory


@pytest.fixture(autouse=True)
def _site_context(mock_site_context):
    """Every test here builds site-aware objects and assigns roles."""


@pytest.mark.django_db
class TestReverseInterface:
    def test_reverses_with_both_kwargs(self):
        organisation = OrganisationFactory()
        url = reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation.slug, "path_string": "cohorts"},
        )
        assert f"organisations/{organisation.slug}/cohorts" in url

    def test_root_reverses_with_no_kwargs(self):
        assert reverse("educator_interface:root") == "/educator/"


@pytest.mark.django_db
class TestInterfaceRoot:
    def test_no_accessible_organisations_raises_404(self):
        user = UserFactory(staff=True)
        request = RequestFactory().get("/educator/")
        request.user = user
        request.session = SessionStore()

        with pytest.raises(Http404):
            interface_root(request)

    def test_redirects_to_the_only_accessible_organisation(self):
        organisation = OrganisationFactory()
        user = UserFactory(staff=True)
        assign_object_role(user, organisation, "organisation_staff")
        request = RequestFactory().get("/educator/")
        request.user = user
        request.session = SessionStore()

        response = interface_root(request)

        assert response.status_code == 302
        assert response.url == reverse(
            "educator_interface:interface",
            kwargs={
                "organisation_slug": organisation.slug,
                "path_string": "cohorts",
            },
        )

    def test_falls_back_to_first_accessible_when_nothing_remembered(self):
        user = UserFactory(staff=True)
        organisation_a = OrganisationFactory(name="Alpha")
        organisation_b = OrganisationFactory(name="Beta")
        assign_object_role(user, organisation_a, "organisation_staff")
        assign_object_role(user, organisation_b, "organisation_staff")
        request = RequestFactory().get("/educator/")
        request.user = user
        request.session = SessionStore()

        response = interface_root(request)

        assert organisation_a.slug in response.url

    def test_redirects_to_the_remembered_organisation_over_the_alphabetical_default(
        self,
    ):
        user = UserFactory(staff=True)
        organisation_a = OrganisationFactory(name="Alpha")
        organisation_b = OrganisationFactory(name="Beta")
        assign_object_role(user, organisation_a, "organisation_staff")
        assign_object_role(user, organisation_b, "organisation_staff")
        request = RequestFactory().get("/educator/")
        request.user = user
        request.session = SessionStore()
        request.session[LAST_ORGANISATION_SESSION_KEY] = organisation_b.slug

        response = interface_root(request)

        assert organisation_b.slug in response.url

    def test_remembered_organisation_is_re_authorised_and_ignored_if_no_longer_accessible(
        self,
    ):
        """The session value is only ever a hint — it is re-checked against
        what the user can currently access, never trusted on its own."""
        user = UserFactory(staff=True)
        accessible_organisation = OrganisationFactory(name="Accessible")
        inaccessible_organisation = OrganisationFactory(name="Inaccessible")
        assign_object_role(user, accessible_organisation, "organisation_staff")
        request = RequestFactory().get("/educator/")
        request.user = user
        request.session = SessionStore()
        request.session[LAST_ORGANISATION_SESSION_KEY] = inaccessible_organisation.slug

        response = interface_root(request)

        assert accessible_organisation.slug in response.url


@pytest.mark.django_db
class TestInterfaceResolvesAndAuthorisesOnce:
    def test_unknown_slug_404s(self):
        user = UserFactory(staff=True)
        request = RequestFactory().get("/educator/organisations/no-such-slug/cohorts")
        request.user = user
        request.session = SessionStore()

        with pytest.raises(Http404):
            interface(request, organisation_slug="no-such-slug", path_string="cohorts")

    def test_slug_exists_but_user_has_no_access_404s(self):
        organisation = OrganisationFactory()
        user = UserFactory(staff=True)
        request = RequestFactory().get(
            f"/educator/organisations/{organisation.slug}/cohorts"
        )
        request.user = user
        request.session = SessionStore()

        with pytest.raises(Http404):
            interface(
                request, organisation_slug=organisation.slug, path_string="cohorts"
            )

    def test_session_write_is_skipped_when_the_value_is_unchanged(self):
        """An unconditional session write would mark the store dirty on
        every educator page load; the guard must only fire on a real change."""
        organisation = OrganisationFactory()
        user = UserFactory(staff=True)
        assign_object_role(user, organisation, "organisation_staff")
        request = RequestFactory().get(
            f"/educator/organisations/{organisation.slug}/cohorts"
        )
        request.user = user
        request.session = SessionStore()
        request.session[LAST_ORGANISATION_SESSION_KEY] = organisation.slug
        request.session.save()
        request.session.modified = False

        interface(request, organisation_slug=organisation.slug, path_string="cohorts")

        assert request.session.modified is False

    def test_session_is_updated_when_the_organisation_changes(self):
        organisation = OrganisationFactory()
        user = UserFactory(staff=True)
        assign_object_role(user, organisation, "organisation_staff")
        request = RequestFactory().get(
            f"/educator/organisations/{organisation.slug}/cohorts"
        )
        request.user = user
        request.session = SessionStore()

        interface(request, organisation_slug=organisation.slug, path_string="cohorts")

        assert request.session[LAST_ORGANISATION_SESSION_KEY] == organisation.slug


@pytest.mark.django_db
class TestSmokeNoReverseMatch:
    """Loads the cohorts list, a cohort detail, and one HTMX panel fetch —
    a NoReverseMatch anywhere in a rendered column or breadcrumb surfaces as
    a hard failure here."""

    def test_cohorts_list_cohort_detail_and_a_panel_fetch_all_render(
        self, logged_in_client
    ):
        organisation = OrganisationFactory()
        user = UserFactory(staff=True)
        assign_object_role(user, organisation, "organisation_staff")
        cohort = CohortFactory(organisation=organisation, name="Smoke Cohort")
        client = logged_in_client(user)

        try:
            list_response = client.get(
                reverse(
                    "educator_interface:interface",
                    kwargs={
                        "organisation_slug": organisation.slug,
                        "path_string": "cohorts",
                    },
                )
            )
            detail_response = client.get(
                reverse(
                    "educator_interface:interface",
                    kwargs={
                        "organisation_slug": organisation.slug,
                        "path_string": f"cohorts/{cohort.pk}",
                    },
                )
            )
            panel_response = client.get(
                reverse(
                    "educator_interface:interface",
                    kwargs={
                        "organisation_slug": organisation.slug,
                        "path_string": f"cohorts/{cohort.pk}/__tabs/details/__panels/details",
                    },
                ),
                HTTP_HX_REQUEST="true",
            )
        except NoReverseMatch:
            pytest.fail("reversing an educator_interface URL raised NoReverseMatch")

        assert list_response.status_code == 200
        assert detail_response.status_code == 200
        assert panel_response.status_code == 200


def _interface_url(organisation_slug: str, path_string: str) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation_slug, "path_string": path_string},
    )


@pytest.mark.django_db
class TestDetailSegmentThatIsNotAUuid:
    """A segment where a detail view expects a pk is whatever the visitor
    typed, so a guessed URL such as cohorts/create has to come back as a
    plain 404 rather than an error page."""

    @pytest.fixture
    def organisation_and_client(self, logged_in_client):
        organisation = OrganisationFactory()
        user = UserFactory(staff=True)
        assign_object_role(user, organisation, "organisation_staff")
        return organisation, logged_in_client(user)

    @pytest.mark.parametrize("segment", ["create", "new", "__create"])
    def test_non_uuid_segment_404s(self, organisation_and_client, segment):
        organisation, client = organisation_and_client

        response = client.get(_interface_url(organisation.slug, f"cohorts/{segment}"))

        assert response.status_code == 404

    def test_well_formed_uuid_for_a_missing_cohort_404s(self, organisation_and_client):
        organisation, client = organisation_and_client

        response = client.get(_interface_url(organisation.slug, f"cohorts/{uuid4()}"))

        assert response.status_code == 404

    def test_real_cohort_id_still_resolves(self, organisation_and_client):
        organisation, client = organisation_and_client
        cohort = CohortFactory(organisation=organisation, name="Resolvable Cohort")

        response = client.get(_interface_url(organisation.slug, f"cohorts/{cohort.pk}"))

        assert response.status_code == 200
