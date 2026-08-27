"""Slug helpers shared by site-aware content models."""

from __future__ import annotations

import contextlib
import uuid

from django.contrib.sites.models import Site
from django.db.models import Model
from django.utils.text import slugify

# What a name is called when nothing in it can be slugified. A name of nothing
# but punctuation reduces to the empty string in every script, and an empty
# slug is not merely ugly: no URL pattern matches it, so the object becomes
# unreachable and any page that reverses a link to it raises NoReverseMatch.
UNSLUGGABLE_NAME_PREFIX = "organisation"


def slug_base_for(name: str) -> str:
    """A non-empty slug base for ``name``, in ``name``'s own script.

    Unicode-preserving, because the ASCII form drops a wholly Cyrillic, Greek
    or CJK name to nothing -- losing the name from the URL for exactly the
    tenants whose name is least guessable from anything else.
    """
    base = slugify(name, allow_unicode=True)
    if base:
        return base
    return f"{UNSLUGGABLE_NAME_PREFIX}-{uuid.uuid4().hex[:8]}"


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
