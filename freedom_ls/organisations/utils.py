"""Standalone lookups that do not belong on the model itself."""

from __future__ import annotations

from django.contrib.sites.models import Site

from freedom_ls.site_aware_models.slugs import get_unique_slug, slug_base_for

from .models import Organisation


def get_default_organisation(site: Site) -> Organisation:
    """The Organisation a Site falls back to when nothing narrower is in scope.

    Guaranteed to exist by the post_save receiver that gives every Site one.
    A DoesNotExist here means that invariant was broken out of band — there is
    no supported path to delete an Organisation — so it should surface as an
    error rather than be silently repaired on a learner-facing path.

    _base_manager, not the site-aware `objects`: the latter would AND the
    ambient thread-local site onto the lookup, which is wrong for a caller
    that has already resolved an explicit `site` (e.g. a management command
    with no request at all).
    """
    return Organisation._base_manager.get(site=site, is_default=True)


def ensure_organisation(
    site: Site, name: str, slug_base: str | None = None
) -> tuple[Organisation, bool]:
    """Get-or-create an Organisation on ``site``, slugged from its name.

    ``slug_base`` overrides the derived base slug, for a caller that wants a
    stable, memorable slug rather than whatever its name derives. The slug is
    only set on creation and never moves on a rename, so such a caller is
    identifying the row by its slug: a row already holding it is returned as
    is, whatever it is called now.
    """
    if slug_base is not None:
        existing = Organisation.objects.filter(site=site, slug=slug_base).first()
        if existing is not None:
            return existing, False
    base = slug_base if slug_base is not None else slug_base_for(name)
    organisation, created = Organisation.objects.get_or_create(
        site=site,
        name=name,
        defaults={"slug": get_unique_slug(Organisation, site, base)},
    )
    return organisation, created
