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

    educator_interface matches organisation_slug against an ASCII-only
    character class, and views.interface reverses that URL with the cohort's
    organisation slug. A slug it cannot express is a NoReverseMatch 500 for
    every educator in that organisation, not a cosmetic problem.
    """
    _seed(qa_site)

    for organisation in Organisation._base_manager.filter(site=qa_site):
        reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation.slug, "path_string": ""},
        )


def test_a_name_that_slugifies_to_nothing_without_a_slug_base_is_refused(qa_site):
    """Failing loudly beats minting an unaddressable slug.

    An empty slug is falsy, so --organisation-slug would silently fall back to
    the site's default organisation and QA would test the wrong data.
    """
    with pytest.raises(Exception, match="slug"):
        _ensure_organisation(qa_site, "Восточно-Европейская Академия")


def test_an_explicit_slug_base_is_used_verbatim(qa_site):
    organisation, _ = _ensure_organisation(
        qa_site, "Восточно-Европейская Академия", slug_base="qa-non-latin"
    )

    assert organisation.slug == "qa-non-latin"
