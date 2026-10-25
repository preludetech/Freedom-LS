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


def test_a_renamed_demo_organisation_is_reused_not_duplicated(mock_site_context):
    site = mock_site_context
    harbour = ensure_demo_organisations(site)[0]
    harbour.name = "Harbour Polytechnic"
    harbour.save(update_fields=["name"])

    ensure_demo_organisations(site)

    assert list(
        Organisation.objects.filter(site=site, slug="harbour-college").values_list(
            "name", flat=True
        )
    ) == ["Harbour Polytechnic"]
    assert not Organisation.objects.filter(site=site, name="Harbour College").exists()
