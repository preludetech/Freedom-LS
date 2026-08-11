"""Tests for OrganisationAdmin."""

from __future__ import annotations

import pytest

from django.contrib import admin
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.organisations.admin import OrganisationAdmin
from freedom_ls.organisations.models import Organisation


@pytest.fixture
def admin_instance() -> OrganisationAdmin:
    return OrganisationAdmin(Organisation, admin.site)


@pytest.fixture
def staff_client(mock_site_context, db):
    user = UserFactory(superuser=True)
    client = Client()
    client.force_login(user)
    return client


class TestDeletePermission:
    def test_delete_permission_is_always_false(
        self, admin_instance: OrganisationAdmin
    ) -> None:
        assert admin_instance.has_delete_permission(request=None) is False


@pytest.mark.django_db
class TestOrganisationAdminSave:
    def test_creating_organisation_via_admin_produces_a_slug(self, staff_client):
        """A freshly-created Organisation gets a non-empty slug from the name."""
        url = reverse("admin:freedom_ls_organisations_organisation_add")

        response = staff_client.post(url, {"name": "Acme Corp"})

        assert response.status_code == 302
        organisation = Organisation.objects.get(name="Acme Corp")
        assert organisation.slug == "acme-corp"

    def test_names_that_slugify_identically_get_distinct_slugs(self, staff_client):
        """Two names that slugify to the same base get -2 appended, not a collision."""
        url = reverse("admin:freedom_ls_organisations_organisation_add")

        staff_client.post(url, {"name": "Acme Corp"})
        staff_client.post(url, {"name": "ACME CORP"})

        slugs = set(
            Organisation.objects.filter(name__in=["Acme Corp", "ACME CORP"])
            .order_by("name")
            .values_list("slug", flat=True)
        )
        assert slugs == {"acme-corp", "acme-corp-2"}
