"""A seeded QA organisation has to be reachable once it exists.

An organisation whose slug the educator interface cannot route to is worse than
one that was never seeded: it looks present in the admin and 500s the moment a
cohort is put in it.
"""

from __future__ import annotations

import pytest

from django.contrib.sites.models import Site
from django.core.management import call_command
from django.urls import reverse

from freedom_ls.organisations.models import Organisation
from freedom_ls.qa_helpers.management.commands.qa_create_organisations import (
    _ensure_organisation,
)

pytestmark = [pytest.mark.fls_internal, pytest.mark.django_db]


@pytest.fixture
def qa_site(mock_site_context: Site) -> Site:
    return mock_site_context


def _seed(site: Site) -> None:
    call_command("qa_create_organisations", site.name)


def test_every_seeded_organisation_slug_reverses_an_educator_interface_url(qa_site):
    """The real contract, through the real URLconf.

    views.interface reverses an educator URL from the cohort's organisation
    slug, so a slug that route cannot express is a NoReverseMatch 500 for every
    educator in that organisation, not a cosmetic problem. The route takes
    unicode, so what is left to get wrong is an empty slug.
    """
    _seed(qa_site)

    for organisation in Organisation._base_manager.filter(site=qa_site):
        reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation.slug, "path_string": ""},
        )


def test_a_non_latin_name_derives_a_slug_in_its_own_script(qa_site):
    organisation, _ = _ensure_organisation(qa_site, "Восточно-Европейская Академия")

    assert organisation.slug == "восточно-европейская-академия"


def test_a_name_that_slugifies_to_nothing_still_gets_a_slug(qa_site):
    """An empty slug is falsy, so --organisation-slug would silently fall back
    to the site's default organisation and QA would test the wrong data."""
    organisation, _ = _ensure_organisation(qa_site, "---")

    assert organisation.slug


def test_an_explicit_slug_base_is_used_verbatim(qa_site):
    organisation, _ = _ensure_organisation(
        qa_site, "Восточно-Европейская Академия", slug_base="qa-non-latin"
    )

    assert organisation.slug == "qa-non-latin"
