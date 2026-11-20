"""Fixtures for the audit log tests."""

from __future__ import annotations

from typing import cast

import pytest

from django.http import HttpRequest
from django.test import RequestFactory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation


@pytest.fixture
def audit_request(
    site_aware_request: RequestFactory,
) -> tuple[HttpRequest, Organisation]:
    organisation = cast(Organisation, OrganisationFactory())
    request = site_aware_request.get("/")
    request.user = UserFactory(superuser=True)
    request.organisation = organisation
    return request, organisation
