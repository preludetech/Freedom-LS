"""Seed four Organisations for QA of the switcher and logo/monogram rendering.

Superseded for a full QA pass by ``qa_create_organisation_scenarios``, which
also seeds the cohorts and personas; this command remains as the smallest
possible organisations-only seed.

Creates (idempotently) four Organisations on the given site, in addition to
the site's own default Organisation:

1. "RPAS Training" — carries a logo, so the logo rendering path is exercised.
2. "Northside" — no logo, so the monogram fallback is exercised. The short
   name is deliberate: the monogram QA renames it to "Northside Academy" and
   expects the initials to change from "NO" to "NA" while the slug stays put.
3. A ~150-character name — long enough to force the report cover's condensed
   wordmark class and to exercise footer truncation.
4. A Cyrillic name — DejaVu Sans (the report's font) covers this script, so
   the render shows real glyphs rather than tofu boxes, isolating the
   download-filename behaviour for a non-Latin name from a missing-glyph
   render.

Usage:
    uv run python manage.py qa_create_organisations
    uv run python manage.py qa_create_organisations --site-name DemoDev
"""

from pathlib import Path

import djclick as click

from django.contrib.sites.models import Site
from django.core.files import File
from django.utils.text import slugify

from freedom_ls.organisations.models import Organisation
from freedom_ls.site_aware_models.slugs import get_unique_slug

LOGO_PATH = Path(__file__).resolve().parent.parent.parent / "fixtures" / "RT-logo.webp"

WITH_LOGO_NAME = "RPAS Training"
WITHOUT_LOGO_NAME = "Northside"
LONG_NAME = (
    "The Northern Federation of Colleges, Universities, Technical Institutes "
    "and Vocational Training Academies for Professional and Continuing Education"
)
NON_LATIN_NAME = "Восточно-Европейская Академия Непрерывного Образования"
# ASCII slugify drops Cyrillic entirely, so this name has no derivable slug.
NON_LATIN_SLUG_BASE = "qa-non-latin-academy"


def _ensure_organisation(
    site: Site, name: str, slug_base: str | None = None
) -> tuple[Organisation, bool]:
    """Get-or-create an Organisation on ``site``, slugged from its name.

    ``slug_base`` overrides the derived base slug. It is required for any name
    that slugifies to the empty string -- a punctuation-only name such as
    "---", or a name in a script ASCII slugify drops entirely -- because an
    empty slug is falsy, so the ``--organisation-slug`` options the other QA
    commands take would silently fall back to the default organisation.
    """
    # ASCII, deliberately: educator_interface routes on
    # (?P<organisation_slug>[-a-zA-Z0-9_]+), and views.interface reverses that
    # URL from a cohort's organisation slug. A unicode slug is a NoReverseMatch
    # 500 for every educator in that organisation, and SlugField's own
    # validator would reject it too -- get_or_create only lets it through
    # because it skips full_clean().
    base = slug_base if slug_base is not None else slugify(name)
    if not base:
        raise click.ClickException(
            f"'{name}' slugifies to nothing. Pass slug_base to give it an "
            f"addressable ASCII slug."
        )
    organisation, created = Organisation.objects.get_or_create(
        site=site,
        name=name,
        defaults={"slug": get_unique_slug(Organisation, site, base)},
    )
    return organisation, created


@click.command()
@click.argument("site_name", default="DemoDev")
def command(site_name: str) -> None:
    """Seed four QA Organisations on SITE_NAME (default: DemoDev)."""
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e

    with_logo, created = _ensure_organisation(site, WITH_LOGO_NAME)
    if not with_logo.logo:
        with LOGO_PATH.open("rb") as fh:
            with_logo.logo.save(LOGO_PATH.name, File(fh), save=True)
    verb = "Created" if created else "Reused"
    click.secho(f"{verb} organisation '{WITH_LOGO_NAME}' (has logo)", fg="green")

    without_logo, created = _ensure_organisation(site, WITHOUT_LOGO_NAME)
    verb = "Created" if created else "Reused"
    click.secho(
        f"{verb} organisation '{WITHOUT_LOGO_NAME}' "
        f"(no logo — initials {without_logo.initials!r})",
        fg="green",
    )

    _, created = _ensure_organisation(site, LONG_NAME)
    verb = "Created" if created else "Reused"
    click.secho(
        f"{verb} organisation '{LONG_NAME}' (long name — condensed wordmark / footer truncation)",
        fg="green",
    )

    _, created = _ensure_organisation(
        site, NON_LATIN_NAME, slug_base=NON_LATIN_SLUG_BASE
    )
    verb = "Created" if created else "Reused"
    click.secho(
        f"{verb} organisation '{NON_LATIN_NAME}' (non-Latin name — unicode download filename)",
        fg="green",
    )
