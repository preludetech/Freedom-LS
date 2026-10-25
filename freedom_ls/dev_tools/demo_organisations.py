"""The organisations the shipped demo courses belong to."""

from __future__ import annotations

from django.contrib.sites.models import Site

from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.utils import ensure_organisation

# (name, slug). The demo course files reference the slug, so the slug is
# passed as the slug base: it stays put if the name is later edited, and a
# re-run finds the renamed row by it rather than creating a second one.
DEMO_ORGANISATIONS: list[tuple[str, str]] = [
    ("Harbour College", "harbour-college"),
    ("Northwind Logistics", "northwind-logistics"),
]


def ensure_demo_organisations(site: Site) -> list[Organisation]:
    """Create the demo organisations on ``site`` if missing and return them."""
    return [
        ensure_organisation(site, name, slug_base=slug)[0]
        for name, slug in DEMO_ORGANISATIONS
    ]
