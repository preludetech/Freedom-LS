"""Fixtures shared across the educator interface tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from freedom_ls.organisations.factories import OrganisationFactory

if TYPE_CHECKING:
    from django.contrib.sites.models import Site


@pytest.fixture
def panel_request(site_aware_request):
    """A request carrying panel_url_kwargs for a real organisation.

    Tables and panels rendered standalone still build links into
    educator_interface:interface, which takes an organisation_slug. The
    interface() view sets these kwargs before dispatch; a test rendering the
    component on its own has to supply them.
    """

    def _make(path: str = "/"):
        organisation = OrganisationFactory()
        request = site_aware_request.get(path)
        request.panel_url_kwargs = {"organisation_slug": organisation.slug}
        request.organisation = organisation
        return request

    return _make


@pytest.fixture
def _site_context(mock_site_context: Site) -> None:
    """Opt-in site context for tests that build site-aware objects.

    Use it through pytest.mark.usefixtures("_site_context").
    """
