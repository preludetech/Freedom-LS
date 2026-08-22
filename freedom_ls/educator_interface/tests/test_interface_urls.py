"""Tests for the educator interface URL shape: the bare-root redirect
(interface_root) and resolving/authorising an organisation once (interface).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from django.contrib.sessions.backends.db import SessionStore
from django.core.handlers.wsgi import WSGIRequest
from django.test import RequestFactory
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.educator_interface.views import (
    LAST_ORGANISATION_SESSION_KEY,
    interface,
)
from freedom_ls.learner_management.factories import CohortFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.role_based_permissions.utils import assign_object_role


@pytest.fixture(autouse=True)
def _site_context(mock_site_context):
    """Every test here builds site-aware objects and assigns roles."""


def _interface_url(organisation_slug: str, path_string: str) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation_slug, "path_string": path_string},
    )


def _remember(client, organisation_slug: str) -> None:
    session = client.session
    session[LAST_ORGANISATION_SESSION_KEY] = organisation_slug
    session.save()


@pytest.mark.django_db
class TestInterfaceRoot:
    def test_no_accessible_organisations_404s(self, logged_in_client):
        client = logged_in_client(UserFactory(staff=True))

        response = client.get(reverse("educator_interface:root"))

        assert response.status_code == 404

    def test_falls_back_to_first_accessible_when_nothing_remembered(
        self, logged_in_client
    ):
        user = UserFactory(staff=True)
        organisation_a = OrganisationFactory(name="Alpha")
        organisation_b = OrganisationFactory(name="Beta")
        assign_object_role(user, organisation_a, "organisation_staff")
        assign_object_role(user, organisation_b, "organisation_staff")
        client = logged_in_client(user)

        response = client.get(reverse("educator_interface:root"))

        assert response.status_code == 302
        assert response["Location"] == _interface_url(organisation_a.slug, "cohorts")

    def test_redirects_to_the_remembered_organisation_over_the_alphabetical_default(
        self, logged_in_client
    ):
        user = UserFactory(staff=True)
        organisation_a = OrganisationFactory(name="Alpha")
        organisation_b = OrganisationFactory(name="Beta")
        assign_object_role(user, organisation_a, "organisation_staff")
        assign_object_role(user, organisation_b, "organisation_staff")
        client = logged_in_client(user)
        _remember(client, organisation_b.slug)

        response = client.get(reverse("educator_interface:root"))

        assert response["Location"] == _interface_url(organisation_b.slug, "cohorts")

    def test_remembered_organisation_is_ignored_if_no_longer_accessible(
        self, logged_in_client
    ):
        """The session value is only ever a hint — it is re-checked against
        what the user can currently access, never trusted on its own."""
        user = UserFactory(staff=True)
        accessible = OrganisationFactory(name="Accessible")
        inaccessible = OrganisationFactory(name="Inaccessible")
        assign_object_role(user, accessible, "organisation_staff")
        client = logged_in_client(user)
        _remember(client, inaccessible.slug)

        response = client.get(reverse("educator_interface:root"))

        assert response["Location"] == _interface_url(accessible.slug, "cohorts")


@pytest.mark.django_db
class TestInterfaceResolvesAndAuthorisesOnce:
    def test_unknown_slug_404s(self, logged_in_client):
        client = logged_in_client(UserFactory(staff=True))

        response = client.get(_interface_url("no-such-slug", "cohorts"))

        assert response.status_code == 404


@pytest.mark.django_db
class TestSessionWrite:
    """These two go through RequestFactory rather than the test client
    because they assert on request.session.modified, which the client does
    not expose."""

    def _request(self, user, organisation_slug: str) -> WSGIRequest:
        request = RequestFactory().get(
            _interface_url(organisation_slug, "cohorts"),
        )
        request.user = user
        request.session = SessionStore()
        return request

    def test_session_write_is_skipped_when_the_value_is_unchanged(self):
        """An unconditional session write would mark the store dirty on
        every educator page load; the guard must only fire on a real change."""
        organisation = OrganisationFactory()
        user = UserFactory(staff=True)
        assign_object_role(user, organisation, "organisation_staff")
        request = self._request(user, organisation.slug)
        request.session[LAST_ORGANISATION_SESSION_KEY] = organisation.slug
        request.session.save()
        request.session.modified = False

        interface(request, organisation_slug=organisation.slug, path_string="cohorts")

        assert request.session.modified is False

    def test_session_is_updated_when_the_organisation_changes(self):
        organisation = OrganisationFactory()
        user = UserFactory(staff=True)
        assign_object_role(user, organisation, "organisation_staff")
        request = self._request(user, organisation.slug)

        interface(request, organisation_slug=organisation.slug, path_string="cohorts")

        assert request.session[LAST_ORGANISATION_SESSION_KEY] == organisation.slug


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
        assert "Resolvable Cohort" in response.content.decode()
