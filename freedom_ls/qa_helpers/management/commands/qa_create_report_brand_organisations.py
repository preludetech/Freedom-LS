"""Seed the extra Organisations the report-branding QA pass needs.

``qa_create_organisations`` covers the four base cases (logo, no logo, very
long name, non-Latin name). The report cover/footer QA also needs the name
lengths *between* "Northside" and the 147-character monster, plus two names
that stress escaping, plus two organisations whose logo file is deliberately
wrong at render time:

1. A ~45-character name, no logo -- the mid-length wordmark budget.
2. A ~40-character name, no logo -- one step shorter, so the point at which
   the cover switches wordmark treatment can be bracketed.
3. ``Acme & Sons <b>Ltd</b> "Trading"`` -- ampersand, angle brackets and
   quotes must survive into the PDF as literal text, not as markup and not as
   ``&amp;``.
4. ``---`` -- a punctuation-only name. ``Organisation.initials`` returns None
   for it, so the monogram fallback has to fall back again.
5. ``QA Logo Vanish`` -- carries a real logo, so QA can delete the file from
   disk afterwards and check the report still renders (the record still points
   at a path; the bytes are gone).
6. ``QA Bad Logo`` -- carries a file named ``logo.png`` whose bytes are plain
   ASCII text. Attached with ``FieldFile.save()``, which does not run the
   model validators, so the row exists in exactly the state a pre-validator
   upload would have left it in. This is deliberate: it exercises the report's
   render-time fallback for an undecodable logo.

Logos are never replaced once set: QA deletes ``QA Logo Vanish``'s file by
hand, and re-running this command must not silently put it back.

Idempotent. Usage:
    uv run python manage.py qa_create_report_brand_organisations
    uv run python manage.py qa_create_report_brand_organisations DemoDev
"""

from pathlib import Path

import djclick as click

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.files import File
from django.core.files.base import ContentFile

from freedom_ls.organisations.models import Organisation
from freedom_ls.qa_helpers.management.commands.qa_create_organisations import (
    LOGO_PATH,
    _ensure_organisation,
)

# Exactly 45 characters.
MEDIUM_NAME = "Riverbend Institute of Applied Technology Ltd"
# Exactly 40 characters.
SHORTER_NAME = "Lakeside College of Health Sciences Inc."
MARKUP_NAME = 'Acme & Sons <b>Ltd</b> "Trading"'
PUNCTUATION_NAME = "---"
# slugify("---") is the empty string, and an empty slug cannot be passed to
# --organisation-slug (it is falsy, so the receiving command silently falls
# back to the site's default organisation).
PUNCTUATION_SLUG_BASE = "qa-punctuation-only"
LOGO_VANISH_NAME = "QA Logo Vanish"
BAD_LOGO_NAME = "QA Bad Logo"

# Plain ASCII, and not a valid image in any format. Kept small on purpose:
# the interesting failure is "Pillow cannot decode this", not "too big".
BAD_LOGO_BYTES = b"this is not an image, it is plain ascii text\n"
BAD_LOGO_FILENAME = "logo.png"


def _describe(organisation: Organisation, created: bool, note: str) -> None:
    verb = "Created" if created else "Reused"
    click.secho(
        f"{verb} organisation {organisation.name!r} "
        f"(slug={organisation.slug!r}, {len(organisation.name)} chars) -- {note}",
        fg="green",
    )


def _logo_absolute_path(organisation: Organisation) -> Path:
    """Where the logo actually sits on disk, for QA to delete or inspect."""
    # .name is typed str | None, but is only None on an empty FieldFile, and
    # every caller here has just checked the field is set.
    return Path(settings.MEDIA_ROOT) / (organisation.logo.name or "")


@click.command()
@click.argument("site_name", default="DemoDev")
def command(site_name: str) -> None:
    """Seed the report-branding QA Organisations on SITE_NAME (default: DemoDev)."""
    try:
        site = Site.objects.get(name=site_name)
    except Site.DoesNotExist as e:
        available = list(Site.objects.values_list("name", flat=True))
        raise click.ClickException(
            f"Site '{site_name}' not found. Available: {available}"
        ) from e

    medium, created = _ensure_organisation(site, MEDIUM_NAME)
    _describe(medium, created, "no logo, mid-length wordmark")

    shorter, created = _ensure_organisation(site, SHORTER_NAME)
    _describe(shorter, created, "no logo, one step shorter")

    markup, created = _ensure_organisation(site, MARKUP_NAME)
    _describe(markup, created, "no logo, must render as literal text")

    punctuation, created = _ensure_organisation(
        site, PUNCTUATION_NAME, slug_base=PUNCTUATION_SLUG_BASE
    )
    _describe(
        punctuation,
        created,
        f"no logo, initials={punctuation.initials!r} (monogram must fall back again)",
    )

    vanish, created = _ensure_organisation(site, LOGO_VANISH_NAME)
    if not vanish.logo:
        with LOGO_PATH.open("rb") as fh:
            vanish.logo.save(LOGO_PATH.name, File(fh), save=True)
    path = _logo_absolute_path(vanish)
    _describe(
        vanish,
        created,
        f"logo at {path} (exists={path.exists()}) -- QA deletes this file by hand",
    )

    bad, created = _ensure_organisation(site, BAD_LOGO_NAME)
    if not bad.logo:
        # FieldFile.save() -> Model.save(), which never calls full_clean(), so
        # validate_organisation_logo does not run. Bypassing it is the point.
        bad.logo.save(BAD_LOGO_FILENAME, ContentFile(BAD_LOGO_BYTES), save=True)
    path = _logo_absolute_path(bad)
    _describe(
        bad,
        created,
        f"NOT-an-image logo at {path} (exists={path.exists()}) -- validators bypassed",
    )
