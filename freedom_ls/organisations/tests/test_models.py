"""Tests for the Organisation model: constraints and the initials property."""

from __future__ import annotations

from pathlib import Path

import pytest

from django.core.files.base import ContentFile
from django.db import IntegrityError

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import (
    Organisation,
    organisation_logo_upload_to,
)
from freedom_ls.role_based_permissions.utils import assign_object_role


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


@pytest.mark.django_db
class TestLogoReplacement:
    """A re-uploaded logo replaces the object at the stable key.

    That mutability is what lets the public alias keep a guessable
    organisations/{pk} key and a one-day cache header instead of an immutable
    one, so it has to hold in development as well as on S3.
    """

    def test_replacing_a_logo_keeps_the_stable_key(self, mock_site_context) -> None:
        organisation = OrganisationFactory()
        organisation.logo.save("first.png", ContentFile(b"first-logo"), save=True)

        organisation.logo.save("second.png", ContentFile(b"second-logo"), save=True)

        assert organisation.logo.name == f"organisations/{organisation.pk}.png"

    def test_replacing_a_logo_leaves_one_file_on_disk(self, mock_site_context) -> None:
        organisation = OrganisationFactory()
        organisation.logo.save("first.png", ContentFile(b"first-logo"), save=True)

        organisation.logo.save("second.png", ContentFile(b"second-logo"), save=True)

        directory = Path(organisation.logo.path).parent
        assert sorted(path.name for path in directory.iterdir()) == [
            f"{organisation.pk}.png"
        ]

    def test_replacing_a_logo_serves_the_new_bytes(self, mock_site_context) -> None:
        organisation = OrganisationFactory()
        organisation.logo.save("first.png", ContentFile(b"first-logo"), save=True)

        organisation.logo.save("second.png", ContentFile(b"second-logo"), save=True)

        assert Path(organisation.logo.path).read_bytes() == b"second-logo"


@pytest.mark.django_db
class TestOrganisationConstraints:
    def test_duplicate_slug_on_same_site_raises_integrity_error(
        self, mock_site_context
    ):
        """The unique_organisation_slug_per_site constraint rejects a collision."""
        OrganisationFactory(slug="acme")

        with pytest.raises(IntegrityError):
            OrganisationFactory(slug="acme")

    def test_duplicate_name_on_same_site_raises_integrity_error(
        self, mock_site_context
    ):
        """The unique_organisation_name_per_site constraint rejects a collision."""
        OrganisationFactory(name="Acme")

        with pytest.raises(IntegrityError):
            OrganisationFactory(name="Acme")

    def test_same_slug_on_different_sites_is_allowed(self, mock_site_context):
        """Slug uniqueness is scoped per site, not global."""
        # Setting site by hand is the deliberate exception to the usual rule:
        # a cross-site test needs a second site the ambient context is not on.
        other_site = SiteFactory(name="OtherSite")

        OrganisationFactory(slug="acme")
        OrganisationFactory(site=other_site, slug="acme")

        assert Organisation._base_manager.filter(slug="acme").count() == 2


@pytest.mark.django_db
class TestOrganisationStaffRole:
    def test_role_holder_may_view_the_organisation(self, mock_site_context):
        """The organisation_staff role grants view_organisation on the object
        it was assigned against, and not on any other organisation."""
        organisation = OrganisationFactory()
        other = OrganisationFactory()
        user = UserFactory()

        assign_object_role(user, organisation, "organisation_staff")

        assert user.has_perm("freedom_ls_organisations.view_organisation", organisation)
        assert not user.has_perm("freedom_ls_organisations.view_organisation", other)
