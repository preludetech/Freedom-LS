"""Tests for OrganisationAdmin."""

from __future__ import annotations

import io
import re
from urllib.parse import unquote

import pytest
from PIL import Image

from django.contrib import admin
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.organisations.admin import (
    ORGANISATION_SUMMARIES,
    SUMMARIES_FIELD,
    OrganisationAdmin,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation

ADD_URL_NAME = "admin:freedom_ls_organisations_organisation_add"
CHANGE_URL_NAME = "admin:freedom_ls_organisations_organisation_change"

_FORMSET_PREFIX = re.compile(r'name="([\w-]+)-TOTAL_FORMS"')


def empty_inline_data(client: Client, url: str) -> dict[str, str]:
    """Management-form keys for whatever inlines other apps have contributed.

    A browser sends these with every change-page submission and the view rejects
    a payload without them. The prefixes are read off the rendered page rather
    than named here, because the inlines belong to apps this one cannot import.

    Every formset comes back empty, which submits no inline changes at all --
    existing rows are left alone, since deleting one needs its own checkbox.
    """
    html = client.get(url).content.decode()
    return {
        f"{prefix}-{key}": "0"
        for prefix in _FORMSET_PREFIX.findall(html)
        for key in ("TOTAL_FORMS", "INITIAL_FORMS", "MIN_NUM_FORMS", "MAX_NUM_FORMS")
    }


@pytest.fixture
def admin_instance() -> OrganisationAdmin:
    return OrganisationAdmin(Organisation, admin.site)


@pytest.fixture
def png_bytes() -> bytes:
    """The smallest PNG the logo validator accepts (its floor is 64x32)."""
    buf = io.BytesIO()
    Image.new("RGB", (64, 32)).save(buf, format="PNG")
    return buf.getvalue()


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

        response = staff_client.post(
            url, {"name": "Westbrook", **empty_inline_data(staff_client, url)}
        )

        assert response.status_code == 302


@pytest.mark.django_db
class TestOrganisationSlugsStayRoutable:
    """Every organisation gets a slug the educator interface can reverse.

    The switcher lists every organisation a user can reach, so one unroutable
    slug does not degrade that organisation alone -- it takes the whole
    educator interface down with a NoReverseMatch.
    """

    def test_a_non_latin_name_keeps_its_own_script(self, staff_client):
        staff_client.post(reverse(ADD_URL_NAME), {"name": "Восточно-Европейская"})

        organisation = Organisation.objects.get(name="Восточно-Европейская")
        assert organisation.slug == "восточно-европейская"

    def test_a_name_of_only_punctuation_still_gets_a_slug(self, staff_client):
        """Nothing survives slugify here, in any script, so a slug is invented."""
        staff_client.post(reverse(ADD_URL_NAME), {"name": "---"})

        organisation = Organisation.objects.get(name="---")
        assert organisation.slug

    @pytest.mark.parametrize(
        "name",
        ["Восточно-Европейская", "Θεσσαλονίκη", "東京アカデミー", "---", "Acme Corp"],
    )
    def test_the_educator_url_reverses_for_the_resulting_slug(self, staff_client, name):
        staff_client.post(reverse(ADD_URL_NAME), {"name": name})
        organisation = Organisation.objects.get(name=name)

        url = reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation.slug, "path_string": "cohorts"},
        )

        # Percent-encoded on the wire, which is what a non-ASCII slug in a path
        # is supposed to look like; decoded is where the slug is legible again.
        assert organisation.slug in unquote(url)


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

    def test_the_dark_variant_is_validated_like_the_light_one(self, staff_client):
        """Both fields reach storage, so both need the same gate in front of them."""
        url = reverse(ADD_URL_NAME)
        upload = SimpleUploadedFile(
            "notes.txt", b"definitely not an image", content_type="text/plain"
        )

        response = staff_client.post(url, {"name": "Westbrook", "logo_on_dark": upload})

        message = " ".join(response.context["adminform"].form.errors["logo_on_dark"])
        assert "PNG" in message
        assert "JPEG" in message
        assert "WebP" in message

    def test_both_variants_upload_together(self, staff_client, png_bytes):
        """Uploaded in one submission, they must not land on each other's path."""
        url = reverse(ADD_URL_NAME)

        response = staff_client.post(
            url,
            {
                "name": "Westbrook",
                "logo": SimpleUploadedFile(
                    "light.png", png_bytes, content_type="image/png"
                ),
                "logo_on_dark": SimpleUploadedFile(
                    "dark.png", png_bytes, content_type="image/png"
                ),
            },
        )

        assert response.status_code == 302
        organisation = Organisation.objects.get(name="Westbrook")
        assert organisation.logo.name != organisation.logo_on_dark.name
        assert organisation.logo_on_dark.name.endswith("-on-dark.png")


@pytest.mark.django_db
class TestContributedExtras:
    """What other apps add to this page, without naming any of them.

    `organisations` cannot import the apps that contribute here, so these tests
    assert the shape of the seam -- present on the change page, absent on the
    add page -- and leave the contributed content itself to be tested by the app
    that owns it.
    """

    def test_the_add_page_offers_no_contributed_inlines(
        self, admin_instance: OrganisationAdmin
    ) -> None:
        assert admin_instance.get_inlines(request=None, obj=None) == []

    def test_the_change_page_offers_every_contributed_inline(
        self, admin_instance: OrganisationAdmin, mock_site_context
    ) -> None:
        organisation = OrganisationFactory()

        assert (
            admin_instance.get_inlines(request=None, obj=organisation)
            == OrganisationAdmin.inlines
        )

    def test_something_is_actually_contributed(
        self, admin_instance: OrganisationAdmin, mock_site_context
    ) -> None:
        """Guards every other test here from passing on an empty seam."""
        organisation = OrganisationFactory()

        assert admin_instance.get_inlines(request=None, obj=organisation)
        assert ORGANISATION_SUMMARIES

    def test_the_change_page_keeps_the_summaries_row(
        self, admin_instance: OrganisationAdmin, mock_site_context
    ) -> None:
        organisation = OrganisationFactory()

        assert SUMMARIES_FIELD in admin_instance.get_fields(
            request=None, obj=organisation
        )

    def test_the_add_page_leaves_out_the_summaries_row(
        self, admin_instance: OrganisationAdmin
    ) -> None:
        fields = admin_instance.get_fields(request=None, obj=None)

        assert SUMMARIES_FIELD not in fields
        assert "name" in fields

    def test_the_summaries_row_goes_away_when_nothing_contributes_one(
        self, admin_instance: OrganisationAdmin, mock_site_context, monkeypatch
    ) -> None:
        """An empty row would otherwise sit on the page of a project that
        installs organisations without any of the apps that fill it."""
        organisation = OrganisationFactory()
        monkeypatch.setattr("freedom_ls.organisations.admin.ORGANISATION_SUMMARIES", [])

        assert SUMMARIES_FIELD not in admin_instance.get_fields(
            request=None, obj=organisation
        )

    def test_the_change_page_renders(self, staff_client) -> None:
        """A smoke test for the contributed inlines: a broken one 500s here."""
        organisation = OrganisationFactory()

        response = staff_client.get(reverse(CHANGE_URL_NAME, args=[organisation.pk]))

        assert response.status_code == 200
