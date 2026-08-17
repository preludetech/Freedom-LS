"""Fixtures shared across the educator interface tests."""

import pytest

from freedom_ls.organisations.factories import OrganisationFactory


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
