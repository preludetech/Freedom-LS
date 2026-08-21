"""Tests for OrganisationAdmin."""

from __future__ import annotations

import pytest

from django.contrib import admin
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.organisations.admin import OrganisationAdmin
from freedom_ls.organisations.models import Organisation

ADD_URL_NAME = "admin:freedom_ls_organisations_organisation_add"


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
        url = reverse(ADD_URL_NAME)

        response = staff_client.post(url, {"name": "Acme Corp"})

        assert response.status_code == 302
        organisation = Organisation.objects.get(name="Acme Corp")
        assert organisation.slug == "acme-corp"

    def test_names_that_slugify_identically_get_distinct_slugs(self, staff_client):
        """Two names that slugify to the same base get -2 appended, not a collision."""
        url = reverse(ADD_URL_NAME)

        staff_client.post(url, {"name": "Acme Corp"})
        staff_client.post(url, {"name": "ACME CORP"})

        slugs = set(
            Organisation.objects.filter(name__in=["Acme Corp", "ACME CORP"])
            .order_by("name")
            .values_list("slug", flat=True)
        )
        assert slugs == {"acme-corp", "acme-corp-2"}

    def test_second_organisation_with_the_same_name_is_rejected(self, staff_client):
        """The per-site name constraint surfaces as a form error, not an IntegrityError."""
        url = reverse(ADD_URL_NAME)
        staff_client.post(url, {"name": "Westbrook"})

        response = staff_client.post(url, {"name": "Westbrook"})

        assert response.status_code == 200
        assert response.context["adminform"].form.errors

    def test_second_organisation_with_the_same_name_is_not_created(self, staff_client):
        """The rejected duplicate leaves exactly one Organisation behind."""
        url = reverse(ADD_URL_NAME)
        staff_client.post(url, {"name": "Westbrook"})

        staff_client.post(url, {"name": "Westbrook"})

        assert Organisation.objects.filter(name="Westbrook").count() == 1

    def test_second_organisation_with_a_different_name_still_saves(self, staff_client):
        """Rejecting duplicates does not block genuinely distinct names."""
        url = reverse(ADD_URL_NAME)
        staff_client.post(url, {"name": "Westbrook"})

        response = staff_client.post(url, {"name": "Eastbrook"})

        assert response.status_code == 302
        assert Organisation.objects.filter(name="Eastbrook").exists()

    def test_resaving_an_organisation_under_its_own_name_is_allowed(self, staff_client):
        """An edit that keeps the name is not mistaken for a duplicate of itself."""
        staff_client.post(reverse(ADD_URL_NAME), {"name": "Westbrook"})
        organisation = Organisation.objects.get(name="Westbrook")
        url = reverse(
            "admin:freedom_ls_organisations_organisation_change", args=[organisation.pk]
        )

        response = staff_client.post(url, {"name": "Westbrook"})

        assert response.status_code == 302


@pytest.mark.django_db
class TestOrganisationAdminLogoUpload:
    def test_text_file_upload_error_names_the_allowed_formats(self, staff_client):
        """A non-image upload is told which formats are allowed, not just that it failed."""
        url = reverse(ADD_URL_NAME)
        upload = SimpleUploadedFile(
            "notes.txt", b"definitely not an image", content_type="text/plain"
        )

        response = staff_client.post(url, {"name": "Westbrook", "logo": upload})

        message = " ".join(response.context["adminform"].form.errors["logo"])
        assert "PNG" in message
        assert "JPEG" in message
        assert "WebP" in message
