"""Fixtures for the audit log tests."""

from __future__ import annotations

import pytest

from django.test import RequestFactory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.organisations.factories import OrganisationFactory


@pytest.fixture
def audit_request(site_aware_request: RequestFactory):
    organisation = OrganisationFactory()
    request = site_aware_request.get("/")
    request.user = UserFactory(superuser=True)
    request.organisation = organisation
    return request, organisation
