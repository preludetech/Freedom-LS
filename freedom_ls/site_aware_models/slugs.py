"""Slug uniqueness helper shared by site-aware content models."""

from __future__ import annotations

import contextlib
import uuid

from django.contrib.sites.models import Site
from django.db.models import Model


def get_unique_slug(
    model_class: type[Model],
    site: Site,
    base_slug: str,
    existing_uuid: str | None = None,
) -> str:
    """Generate a unique slug for ``model_class`` on ``site``, appending -2, -3, etc. if needed.

    Args:
        model_class: The model class (must have ``site`` and ``slug`` fields).
        site: The site to scope the uniqueness check to.
        base_slug: The base slug to make unique.
        existing_uuid: Optional UUID of an existing object (excluded from the check).

    Returns:
        A unique slug for the given site and model.
    """
    slug = base_slug
    counter = 2

    while True:
        # _base_manager, not the site-aware `objects`: the latter also ANDs in
        # whatever site is ambient on the thread-local request, so a caller
        # passing a `site` other than the ambient one would have every
        # candidate slug reported as free.
        queryset = model_class._base_manager.filter(site=site, slug=slug)

        if existing_uuid:
            with contextlib.suppress(ValueError, AttributeError):
                queryset = queryset.exclude(id=uuid.UUID(existing_uuid))

        if not queryset.exists():
            return slug

        slug = f"{base_slug}-{counter}"
        counter += 1
