"""Keeps every Site carrying an Organisation named after itself."""

from __future__ import annotations

from django.contrib.sites.models import Site
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify

from freedom_ls.site_aware_models.slugs import get_unique_slug

from .models import Organisation


@receiver(post_save, sender=Site)
def ensure_default_organisation(
    sender: type[Site], instance: Site, **kwargs: object
) -> None:
    """Every Site carries an Organisation named after itself.

    A receiver rather than an edit to create_site so site_aware_models keeps
    its zero outgoing edges, and so the admin, the shell and SiteFactory are
    covered too. get_or_create, not the `created` flag: re-saving a Site (a
    domain change, say) must never produce a second Organisation.

    _base_manager throughout: the site-aware manager would AND the ambient
    thread-local site onto the lookup, and the Site being saved is frequently
    not the Site the current request is for. Using `objects` here would make
    the lookup half of get_or_create miss every time a different site is
    ambient, so a re-save would attempt a second INSERT and hit the
    unique-name constraint instead of finding the row that already exists.
    """
    Organisation._base_manager.get_or_create(
        site=instance,
        name=instance.name,
        defaults={
            "slug": get_unique_slug(Organisation, instance, slugify(instance.name))
        },
    )
