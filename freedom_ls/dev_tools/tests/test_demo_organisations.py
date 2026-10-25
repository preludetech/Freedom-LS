"""The demo organisations are created idempotently, with stable slugs."""

from __future__ import annotations

import pytest

from freedom_ls.dev_tools.demo_organisations import ensure_demo_organisations
from freedom_ls.organisations.models import Organisation

pytestmark = [pytest.mark.django_db, pytest.mark.dev_tooling]


def test_calling_twice_leaves_two_demo_organisations(mock_site_context):
    site = mock_site_context
    ensure_demo_organisations(site)

    ensure_demo_organisations(site)

    assert (
        Organisation.objects.filter(
            site=site, slug__in=["harbour-college", "northwind-logistics"]
        ).count()
        == 2
    )
