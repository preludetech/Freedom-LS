"""Tests for get_default_organisation."""

from __future__ import annotations

import pytest

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
