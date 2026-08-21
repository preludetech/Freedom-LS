"""Tests for the post_save receiver that keeps every Site's default Organisation in sync."""

from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import SiteFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.signals import (
    ensure_default_organisations_after_migrate,
)


@pytest.mark.django_db
class TestEnsureDefaultOrganisation:
    def test_organisation_lands_on_the_new_site_not_the_ambient_one(
        self, mock_site_context
    ):
        """mock_site_context makes a different Site ambient. The Organisation
        for a newly-created Site must still land on that new Site, proving
        the receiver does not read the ambient thread-local site."""
        new_site = SiteFactory(name="ForeignSite")

        organisation = Organisation._base_manager.get(site=new_site)
        assert organisation.name == "ForeignSite"

    def test_renaming_a_site_does_not_create_a_second_organisation(
        self, mock_site_context
    ):
        """A rename is the case a name-keyed get_or_create misses: the lookup
        finds nothing under the new name and inserts a duplicate, which then
        wins get_default_organisation while every Cohort stays on the original.

        The Organisation keeps its original name on purpose — the name is
        admin-editable, so the receiver must not clobber it on every Site save.
        """
        new_site = SiteFactory(name="Before Rename")

        new_site.name = "After Rename"
        new_site.save()

        assert Organisation._base_manager.filter(site=new_site).count() == 1
        default = Organisation._base_manager.get(site=new_site, is_default=True)
        assert default.name == "Before Rename"

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


@pytest.mark.django_db
class TestEnsureDefaultOrganisationsAfterMigrate:
    """The post_migrate safety net for the Site that migrate creates itself.

    django.contrib.sites builds that Site from the historical model in the
    migration state, so the post_save receiver never fires for it and a fresh
    database would otherwise finish migrating with no Organisation at all.
    """

    def test_gives_a_site_with_no_organisation_a_default_one(self, mock_site_context):
        site = mock_site_context
        Organisation._base_manager.filter(site=site).delete()

        ensure_default_organisations_after_migrate()

        default = Organisation._base_manager.get(site=site, is_default=True)
        assert default.name == site.name

    def test_is_idempotent_so_it_is_safe_on_every_migrate(self, mock_site_context):
        """It runs on every migrate, not only the first."""
        site = mock_site_context

        ensure_default_organisations_after_migrate()
        ensure_default_organisations_after_migrate()

        assert Organisation._base_manager.filter(site=site).count() == 1
