"""Factories for organisations models."""

import factory

from freedom_ls.site_aware_models.factories import SiteAwareFactory
from freedom_ls.site_aware_models.slugs import get_unique_slug, slug_base_for

from .models import Organisation


class OrganisationFactory(SiteAwareFactory):
    """Factory for creating Organisation instances."""

    class Meta:
        model = Organisation

    name = factory.Sequence(lambda n: f"Organisation {n}")
    slug = factory.LazyAttribute(
        lambda o: get_unique_slug(Organisation, o.site, slug_base_for(o.name))
    )
