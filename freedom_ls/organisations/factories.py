"""Factories for organisations models."""

import factory

from django.utils.text import slugify

from freedom_ls.site_aware_models.factories import SiteAwareFactory
from freedom_ls.site_aware_models.slugs import get_unique_slug

from .models import Organisation


class OrganisationFactory(SiteAwareFactory):
    """Factory for creating Organisation instances."""

    class Meta:
        model = Organisation

    name = factory.Sequence(lambda n: f"Organisation {n}")
    slug = factory.LazyAttribute(
        lambda o: get_unique_slug(Organisation, o.site, slugify(o.name))
    )
