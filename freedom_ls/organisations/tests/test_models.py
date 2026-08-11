"""Tests for the Organisation model: constraints and the initials property."""

from __future__ import annotations

import pytest

from django.db import IntegrityError

from freedom_ls.accounts.factories import SiteFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation


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
        other_site = SiteFactory(name="OtherSite")

        first = OrganisationFactory(slug="acme")
        second = OrganisationFactory(site=other_site, slug="acme")

        assert first.slug == second.slug
        assert first.site != second.site
