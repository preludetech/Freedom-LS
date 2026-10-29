"""Seed six Organisations for QA of the switcher and logo/monogram rendering.

Superseded for a full QA pass by ``qa_create_organisation_scenarios``, which
also seeds the cohorts and personas; this command remains as the smallest
possible organisations-only seed.

Creates (idempotently) six Organisations on the given site, in addition to
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
5. "Skyline Aviation" — carries a profile logo and a bio, so the round mark
   and the organisation card's bio line are exercised.
6. "Coastal Flight School" — carries a wide logo, no profile logo and no bio,
   so the mark's fallback to the light-background logo and the card without a
   bio are exercised.

Usage:
    uv run python manage.py qa_create_organisations
    uv run python manage.py qa_create_organisations DemoDev
"""

from pathlib import Path

import djclick as click

from django.contrib.sites.models import Site
from django.core.files import File

from freedom_ls.organisations.utils import ensure_organisation

_FIXTURES = Path(__file__).resolve().parent.parent.parent / "fixtures"

LOGO_PATH = _FIXTURES / "RT-logo.webp"
# A real light/dark pair, so an organisation carrying both can be checked
# against a mark that genuinely changes with the background rather than the
# same file twice.
LOGO_LIGHT_PATH = _FIXTURES / "fc-light-bg.png"
LOGO_DARK_PATH = _FIXTURES / "fc-dark-bg.png"

WITH_LOGO_NAME = "RPAS Training"
WITHOUT_LOGO_NAME = "Northside"
LONG_NAME = (
    "The Northern Federation of Colleges, Universities, Technical Institutes "
    "and Vocational Training Academies for Professional and Continuing Education"
)
NON_LATIN_NAME = "Восточно-Европейская Академия Непрерывного Образования"
WITH_PROFILE_LOGO_NAME = "Skyline Aviation"
WITH_PROFILE_LOGO_BIO = (
    "Skyline Aviation trains remote pilots for commercial survey work. "
    "Its courses cover airspace rules, flight planning and safe operations."
)
WIDE_LOGO_NAME = "Coastal Flight School"
PROFILE_LOGO_PATH = _FIXTURES / "dronex-logo.png"
WIDE_LOGO_PATH = _FIXTURES / "fc-light-bg.png"


@click.command()
@click.argument("site_name", default="DemoDev")
def command(site_name: str) -> None:
    """Seed six QA Organisations on SITE_NAME (default: DemoDev)."""
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e

    with_logo, created = ensure_organisation(site, WITH_LOGO_NAME)
    if not with_logo.logo:
        with LOGO_PATH.open("rb") as fh:
            with_logo.logo.save(LOGO_PATH.name, File(fh), save=True)
    verb = "Created" if created else "Reused"
    click.secho(f"{verb} organisation '{WITH_LOGO_NAME}' (has logo)", fg="green")

    without_logo, created = ensure_organisation(site, WITHOUT_LOGO_NAME)
    verb = "Created" if created else "Reused"
    click.secho(
        f"{verb} organisation '{WITHOUT_LOGO_NAME}' "
        f"(no logo — initials {without_logo.initials!r})",
        fg="green",
    )

    _, created = ensure_organisation(site, LONG_NAME)
    verb = "Created" if created else "Reused"
    click.secho(
        f"{verb} organisation '{LONG_NAME}' (long name — condensed wordmark / footer truncation)",
        fg="green",
    )

    _, created = ensure_organisation(site, NON_LATIN_NAME)
    verb = "Created" if created else "Reused"
    click.secho(
        f"{verb} organisation '{NON_LATIN_NAME}' (non-Latin name — unicode download filename)",
        fg="green",
    )

    with_profile_logo, created = ensure_organisation(site, WITH_PROFILE_LOGO_NAME)
    if not with_profile_logo.profile_logo:
        with PROFILE_LOGO_PATH.open("rb") as fh:
            with_profile_logo.profile_logo.save(
                PROFILE_LOGO_PATH.name, File(fh), save=True
            )
    if not with_profile_logo.bio:
        with_profile_logo.bio = WITH_PROFILE_LOGO_BIO
        with_profile_logo.save(update_fields=["bio"])
    verb = "Created" if created else "Reused"
    click.secho(
        f"{verb} organisation '{WITH_PROFILE_LOGO_NAME}' (profile logo and bio)",
        fg="green",
    )

    wide_logo, created = ensure_organisation(site, WIDE_LOGO_NAME)
    if not wide_logo.logo:
        with WIDE_LOGO_PATH.open("rb") as fh:
            wide_logo.logo.save(WIDE_LOGO_PATH.name, File(fh), save=True)
    verb = "Created" if created else "Reused"
    click.secho(
        f"{verb} organisation '{WIDE_LOGO_NAME}' (wide logo, no profile logo, no bio)",
        fg="green",
    )
