"""Tests for the Organisation model: constraints and the initials property."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.forms import modelform_factory

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import (
    Organisation,
    organisation_logo_on_dark_upload_to,
    organisation_logo_upload_to,
)
from freedom_ls.role_based_permissions.utils import assign_object_role


def _jpeg_upload(name: str) -> SimpleUploadedFile:
    """A real JPEG, since the logo validators decode the bytes rather than trust
    the extension."""
    buffer = io.BytesIO()
    Image.new("RGB", (200, 100)).save(buffer, format="JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


class TestInitials:
    def test_two_token_name_uses_first_letter_of_each_token(self) -> None:
        assert Organisation(name="RPAS Training").initials == "RT"

    def test_single_token_name_uses_first_two_letters(self) -> None:
        assert Organisation(name="Northside").initials == "NO"

    def test_single_character_name_returns_that_character(self) -> None:
        assert Organisation(name="X").initials == "X"

    def test_non_alphabetic_name_returns_none(self) -> None:
        assert Organisation(name="12345").initials is None

    def test_non_latin_single_token_name_returns_single_grapheme(self) -> None:
        assert Organisation(name="北京").initials == "北"


class TestLogoUploadPath:
    """The stored path is built from the pk and extension only. Interpolating
    the uploaded filename would allow path traversal."""

    def test_path_is_the_pk_and_extension(self) -> None:
        organisation = Organisation(name="Acme")

        path = organisation_logo_upload_to(organisation, "whatever.PNG")

        assert path == f"organisations/{organisation.pk}.png"

    def test_traversal_in_the_uploaded_filename_is_discarded(self) -> None:
        organisation = Organisation(name="Acme")

        path = organisation_logo_upload_to(organisation, "../../../etc/passwd.png")

        assert path == f"organisations/{organisation.pk}.png"

    def test_the_dark_variant_takes_a_suffix_of_its_own(self) -> None:
        organisation = Organisation(name="Acme")

        path = organisation_logo_on_dark_upload_to(organisation, "whatever.PNG")

        assert path == f"organisations/{organisation.pk}-on-dark.png"

    def test_traversal_in_the_dark_variants_filename_is_discarded(self) -> None:
        organisation = Organisation(name="Acme")

        path = organisation_logo_on_dark_upload_to(
            organisation, "../../../etc/passwd.png"
        )

        assert path == f"organisations/{organisation.pk}-on-dark.png"

    def test_the_two_variants_never_share_a_path(self) -> None:
        """Without the suffix the second upload would overwrite the first."""
        organisation = Organisation(name="Acme")

        assert organisation_logo_upload_to(
            organisation, "logo.png"
        ) != organisation_logo_on_dark_upload_to(organisation, "logo.png")


@pytest.mark.django_db
class TestLogoReplacement:
    """A re-uploaded logo replaces the object at the stable key.

    That mutability is what lets the public alias keep a guessable
    organisations/{pk} key and a one-day cache header instead of an immutable
    one, so it has to hold in development as well as on S3.
    """

    def test_replacing_a_logo_keeps_the_stable_key(
        self, mock_site_context: object
    ) -> None:
        organisation = OrganisationFactory()
        organisation.logo.save("first.png", ContentFile(b"first-logo"), save=True)

        organisation.logo.save("second.png", ContentFile(b"second-logo"), save=True)

        assert organisation.logo.name == f"organisations/{organisation.pk}.png"

    def test_replacing_a_logo_leaves_one_file_on_disk(
        self, mock_site_context: object
    ) -> None:
        organisation = OrganisationFactory()
        organisation.logo.save("first.png", ContentFile(b"first-logo"), save=True)

        organisation.logo.save("second.png", ContentFile(b"second-logo"), save=True)

        directory = Path(organisation.logo.path).parent
        assert sorted(path.name for path in directory.iterdir()) == [
            f"{organisation.pk}.png"
        ]

    def test_replacing_a_logo_serves_the_new_bytes(
        self, mock_site_context: object
    ) -> None:
        organisation = OrganisationFactory()
        organisation.logo.save("first.png", ContentFile(b"first-logo"), save=True)

        organisation.logo.save("second.png", ContentFile(b"second-logo"), save=True)

        assert Path(organisation.logo.path).read_bytes() == b"second-logo"

    def test_replacing_a_logo_with_another_extension_moves_the_key(
        self, mock_site_context: object
    ) -> None:
        organisation = OrganisationFactory()
        organisation.logo.save("first.png", ContentFile(b"first-logo"), save=True)

        organisation.logo.save("second.jpg", ContentFile(b"second-logo"), save=True)

        assert organisation.logo.name == f"organisations/{organisation.pk}.jpg"

    def test_replacing_a_logo_with_another_extension_leaves_one_file(
        self, mock_site_context: object
    ) -> None:
        """Overwriting only covers a replacement at the same key. Four extensions
        are allowed, so a PNG replaced by a JPEG writes a second object — and this
        bucket is anonymously readable, which would leave the superseded logo
        publicly fetchable for good."""
        organisation = OrganisationFactory()
        organisation.logo.save("first.png", ContentFile(b"first-logo"), save=True)

        organisation.logo.save("second.jpg", ContentFile(b"second-logo"), save=True)

        directory = Path(organisation.logo.path).parent
        assert sorted(path.name for path in directory.iterdir()) == [
            f"{organisation.pk}.jpg"
        ]

    def test_clearing_a_logo_removes_the_object(
        self, mock_site_context: object
    ) -> None:
        organisation = OrganisationFactory()
        organisation.logo.save("first.png", ContentFile(b"first-logo"), save=True)
        directory = Path(organisation.logo.path).parent

        organisation.logo = ""
        organisation.save()

        assert list(directory.iterdir()) == []

    def test_saving_without_touching_the_logo_keeps_it(
        self, mock_site_context: object
    ) -> None:
        organisation = OrganisationFactory()
        organisation.logo.save("first.png", ContentFile(b"first-logo"), save=True)

        organisation.name = "Renamed"
        organisation.save()

        assert Path(organisation.logo.path).read_bytes() == b"first-logo"

    def test_an_admin_form_upload_replaces_its_logo_cleanly(
        self, mock_site_context: object
    ) -> None:
        """The path an admin actually takes. A form assigns the upload and lets
        FileField.pre_save write it during save(), so the new key only exists
        partway through — later than logo.save() sets it, and the previous name
        has to still be readable at that point."""
        organisation = OrganisationFactory()
        organisation.logo.save("first.png", ContentFile(b"first-logo"), save=True)
        directory = Path(organisation.logo.path).parent
        form_class = modelform_factory(Organisation, fields=["name", "slug", "logo"])

        form = form_class(
            data={"name": organisation.name, "slug": organisation.slug},
            files={"logo": _jpeg_upload("second.jpg")},
            instance=Organisation.objects.get(pk=organisation.pk),
        )
        assert form.is_valid(), form.errors
        form.save()

        assert sorted(path.name for path in directory.iterdir()) == [
            f"{organisation.pk}.jpg"
        ]

    def test_a_reloaded_instance_replaces_its_logo_cleanly(
        self, mock_site_context: object
    ) -> None:
        organisation = OrganisationFactory()
        organisation.logo.save("first.png", ContentFile(b"first-logo"), save=True)

        reloaded = Organisation.objects.get(pk=organisation.pk)
        reloaded.logo.save("second.webp", ContentFile(b"second-logo"), save=True)

        directory = Path(reloaded.logo.path).parent
        assert sorted(path.name for path in directory.iterdir()) == [
            f"{organisation.pk}.webp"
        ]

    def test_replacing_the_dark_variant_leaves_no_superseded_object(
        self, mock_site_context: object
    ) -> None:
        """The dark variant shares the anonymously-readable bucket, so it needs
        the same sweep — an abandoned object there stays fetchable for good."""
        organisation = OrganisationFactory()
        organisation.logo_on_dark.save(
            "first.png", ContentFile(b"first-logo"), save=True
        )

        organisation.logo_on_dark.save(
            "second.jpg", ContentFile(b"second-logo"), save=True
        )

        directory = Path(organisation.logo_on_dark.path).parent
        assert sorted(path.name for path in directory.iterdir()) == [
            f"{organisation.pk}-on-dark.jpg"
        ]

    def test_replacing_one_variant_leaves_the_other_alone(
        self, mock_site_context: object
    ) -> None:
        """The sweep is per field. Deleting by pk prefix would take both."""
        organisation = OrganisationFactory()
        organisation.logo.save("light.png", ContentFile(b"light-logo"), save=True)
        organisation.logo_on_dark.save("dark.png", ContentFile(b"dark-logo"), save=True)

        organisation.logo.save("light.jpg", ContentFile(b"new-light"), save=True)

        assert Path(organisation.logo_on_dark.path).read_bytes() == b"dark-logo"


@pytest.mark.django_db
class TestOrganisationConstraints:
    def test_duplicate_slug_on_same_site_raises_integrity_error(
        self, mock_site_context: object
    ):
        """The unique_organisation_slug_per_site constraint rejects a collision."""
        OrganisationFactory(slug="acme")

        with pytest.raises(IntegrityError):
            OrganisationFactory(slug="acme")

    def test_duplicate_name_on_same_site_raises_integrity_error(
        self, mock_site_context: object
    ):
        """The unique_organisation_name_per_site constraint rejects a collision."""
        OrganisationFactory(name="Acme")

        with pytest.raises(IntegrityError):
            OrganisationFactory(name="Acme")

    def test_same_slug_on_different_sites_is_allowed(self, mock_site_context: object):
        """Slug uniqueness is scoped per site, not global."""
        # Setting site by hand is the deliberate exception to the usual rule:
        # a cross-site test needs a second site the ambient context is not on.
        other_site = SiteFactory(name="OtherSite")

        OrganisationFactory(slug="acme")
        OrganisationFactory(site=other_site, slug="acme")

        assert Organisation._base_manager.filter(slug="acme").count() == 2


@pytest.mark.django_db
class TestOrganisationStaffRole:
    def test_role_holder_may_view_the_organisation(self, mock_site_context: object):
        """The organisation_staff role grants view_organisation on the object
        it was assigned against, and not on any other organisation."""
        organisation = OrganisationFactory()
        other = OrganisationFactory()
        user = UserFactory()

        assign_object_role(user, organisation, "organisation_staff")

        assert user.has_perm("freedom_ls_organisations.view_organisation", organisation)
        assert not user.has_perm("freedom_ls_organisations.view_organisation", other)
