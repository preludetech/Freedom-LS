"""Fixtures shared across the educator interface tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, cast

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser
    from django.contrib.sites.models import Site
    from django.test import Client

    from freedom_ls.learner_management.models import Cohort


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


@pytest.fixture
def role_holder_client(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> Callable[[Organisation | Cohort, str], Client]:
    """Factory: a logged-in staff user holding `role` on `target`."""

    def _make(
        target: Organisation | Cohort, role: str = "organisation_admin"
    ) -> Client:
        user = UserFactory(staff=True)
        assign_role(UserFactory(superuser=True), user, role, target)
        return logged_in_client(user)

    return _make


@pytest.fixture
def organisation(mock_site_context: Site) -> Organisation:
    return cast(Organisation, OrganisationFactory())
