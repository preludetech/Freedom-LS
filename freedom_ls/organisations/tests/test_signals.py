"""Tests for the post_save receiver that keeps every Site's default Organisation in sync."""

from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import SiteFactory
from freedom_ls.organisations.models import Organisation


@pytest.mark.django_db
class TestEnsureDefaultOrganisation:
    def test_new_site_gets_exactly_one_organisation(self):
        site = SiteFactory(name="Acme")

        assert Organisation._base_manager.filter(site=site).count() == 1

    def test_organisation_lands_on_the_new_site_not_the_ambient_one(
        self, mock_site_context
    ):
        """mock_site_context makes a different Site ambient. The Organisation
        for a newly-created Site must still land on that new Site, proving
        the receiver does not read the ambient thread-local site."""
        new_site = SiteFactory(name="ForeignSite")

        organisation = Organisation._base_manager.get(site=new_site)
        assert organisation.name == "ForeignSite"

    def test_resaving_a_site_under_a_foreign_ambient_site_does_not_duplicate(
        self, mock_site_context
    ):
        """The bug this receiver must avoid: objects.get_or_create's lookup
        half would AND the ambient thread-local site onto the query, so a
        re-save of a Site created under a foreign ambient site would miss the
        row that already exists and attempt a second INSERT, raising
        IntegrityError on unique_organisation_name_per_site. A test that only
        creates once passes against that broken version too."""
        new_site = SiteFactory(name="ForeignSite2")

        new_site.save()

        assert Organisation._base_manager.filter(site=new_site).count() == 1
