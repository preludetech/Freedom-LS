"""Standalone lookups that do not belong on the model itself."""

from __future__ import annotations

from django.contrib.sites.models import Site

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
