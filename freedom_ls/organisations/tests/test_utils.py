"""Tests for get_default_organisation."""

from __future__ import annotations

import pytest

from django.db import IntegrityError

from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.utils import get_default_organisation


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
