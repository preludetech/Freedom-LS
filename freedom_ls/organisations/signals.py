"""Keeps every Site carrying a default Organisation."""

from __future__ import annotations

from django.contrib.sites.models import Site
from django.db.models.signals import post_save
from django.dispatch import receiver

from freedom_ls.site_aware_models.slugs import get_unique_slug, slug_base_for

from .models import Organisation


def _ensure_default_organisation(site: Site) -> None:
    """Give one Site its default Organisation, seeded from the Site's name.

    get_or_create, not a bare create: this runs on every Site save and on
    every migrate, so it has to be idempotent.

    The lookup keys on is_default, not on the name. The name only seeds the
    new row: it is editable in the admin, and a Site rename does not propagate
    to it, so keying on it would miss an Organisation that already exists and
    insert a duplicate — leaving every Cohort and registration attached to a
    default that is no longer reachable as one. The Site's name is a starting
    point for the Organisation's, not an identity for it.

    _base_manager throughout: the site-aware manager would AND the ambient
    thread-local site onto the lookup, and the Site being handled is
    frequently not the Site the current request is for. Using `objects` here
    would make the lookup half of get_or_create miss every time a different
    site is ambient, so a re-save would attempt a second INSERT and hit the
    unique-name constraint instead of finding the row that already exists.
    """
    Organisation._base_manager.get_or_create(
        site=site,
        is_default=True,
        defaults={
            "name": site.name,
            "slug": get_unique_slug(Organisation, site, slug_base_for(site.name)),
        },
    )


@receiver(post_save, sender=Site)
def ensure_default_organisation(
    sender: type[Site], instance: Site, **kwargs: object
) -> None:
    """Every Site saved at runtime carries a default Organisation.

    A receiver rather than an edit to create_site so site_aware_models keeps
    its zero outgoing edges, and so the admin, the shell and SiteFactory are
    covered too.
    """
    _ensure_default_organisation(instance)


def ensure_default_organisations_after_migrate(**kwargs: object) -> None:
    """Cover the Site that migrate itself creates.

    django.contrib.sites' own post_migrate hook builds the default Site from
    the *historical* model in the migration state, so the post_save it emits
    carries a sender that is not django.contrib.sites.models.Site and the
    receiver above never runs. A freshly created database would therefore
    finish migrating with a Site and no Organisation at all, and every lookup
    of the default would raise DoesNotExist on a learner-facing path.

    Connected against this app's config in apps.py, which INSTALLED_APPS
    places after django.contrib.sites — so by the time this runs, the default
    Site exists.
    """
    for site in Site.objects.all():
        _ensure_default_organisation(site)
