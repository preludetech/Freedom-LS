"""The organisations the shipped demo courses belong to."""

from __future__ import annotations

from django.contrib.sites.models import Site

from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.utils import ensure_organisation

# (name, slug, bio). The demo course files reference the slug, so the slug is
# passed as the slug base: it stays put if the name is later edited, and a
# re-run finds the renamed row by it rather than creating a second one.
DEMO_ORGANISATIONS: list[tuple[str, str, str]] = [
    (
        "Harbour College",
        "harbour-college",
        "Harbour College is a vocational college on the waterfront. It teaches "
        "workplace safety and port operations to people starting out in the trades.",
    ),
    (
        "Northwind Logistics",
        "northwind-logistics",
        "Northwind Logistics moves freight across three countries. Its courses "
        "cover warehouse safety, driver compliance and supply-chain basics.",
    ),
]


def ensure_demo_organisations(site: Site) -> list[Organisation]:
    """Create the demo organisations on ``site`` if missing, set their bios, and return them."""
    organisations = []
    for name, slug, bio in DEMO_ORGANISATIONS:
        organisation, _ = ensure_organisation(site, name, slug_base=slug)
        if organisation.bio != bio:
            organisation.bio = bio
            organisation.save(update_fields=["bio"])
        organisations.append(organisation)
    return organisations
