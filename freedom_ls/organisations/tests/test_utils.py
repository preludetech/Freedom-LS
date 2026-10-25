"""Tests for get_default_organisation."""

from __future__ import annotations

import pytest

from django.db import IntegrityError

from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.utils import (
    ensure_organisation,
    get_default_organisation,
)


@pytest.mark.django_db
def test_returns_the_organisation_named_after_the_site(mock_site_context):
    """The post_save receiver already created a same-named Organisation."""
    site = mock_site_context

    organisation = get_default_organisation(site)

    assert organisation.name == site.name
    assert organisation.site == site


@pytest.mark.django_db
def test_raises_when_the_default_organisation_is_missing(mock_site_context):
    """A missing default Organisation is an operator error, not silently repaired."""
    site = mock_site_context
    Organisation._base_manager.filter(site=site).delete()

    with pytest.raises(Organisation.DoesNotExist):
        get_default_organisation(site)


@pytest.mark.django_db
def test_picks_the_flagged_organisation_out_of_several_on_one_site(mock_site_context):
    """A Site has many Organisations and only one of them is the default.

    The default is also renamed here, so nothing can resolve it by matching
    the Site's name.
    """
    site = mock_site_context
    default = get_default_organisation(site)
    default.name = "Renamed Away From The Site"
    default.save()
    OrganisationFactory(site=site)
    OrganisationFactory(site=site)

    assert get_default_organisation(site) == default


@pytest.mark.django_db
def test_a_site_cannot_hold_two_default_organisations(mock_site_context):
    """The partial unique constraint is what makes the receiver's
    get_or_create on (site, is_default) resolve to exactly one row."""
    with pytest.raises(IntegrityError):
        OrganisationFactory(site=mock_site_context, is_default=True)


@pytest.mark.django_db
def test_ensure_organisation_reuses_an_existing_row(mock_site_context):
    site = mock_site_context
    first, created_first = ensure_organisation(site, "Reuse Me")

    second, created_second = ensure_organisation(site, "Reuse Me")

    assert (created_first, created_second) == (True, False)
    assert second == first


@pytest.mark.django_db
def test_ensure_organisation_slugs_from_the_slug_base(mock_site_context):
    organisation, _ = ensure_organisation(
        mock_site_context, "Some Name", slug_base="fixed-slug"
    )

    assert organisation.slug == "fixed-slug"


@pytest.mark.django_db
def test_ensure_organisation_finds_a_renamed_row_by_its_slug(mock_site_context):
    site = mock_site_context
    first, _ = ensure_organisation(site, "Old Name", slug_base="fixed-slug")
    first.name = "New Name"
    first.save(update_fields=["name"])

    second, created = ensure_organisation(site, "Old Name", slug_base="fixed-slug")

    assert (second, created) == (first, False)
    assert Organisation.objects.filter(site=site, slug="fixed-slug").count() == 1
