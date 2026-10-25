"""Factories for rows that belong to no FLS app."""

import factory

from django.contrib.sites.models import Site


class SiteFactory(factory.django.DjangoModelFactory):
    """Factory for django.contrib.sites.models.Site.

    NOT a SiteAwareFactory — Site is the site dimension, not a site-aware model.
    The Site this factory creates is the kind of object you might pass into
    `mock_site_context`, not one created under it.
    """

    class Meta:
        model = Site
        # Site.domain is unique. Keying on name too means an identical call returns
        # the existing row, while a call that reuses a domain under another name
        # raises IntegrityError instead of quietly returning the wrong Site.
        django_get_or_create = ("domain", "name")

    name = factory.Sequence(lambda n: f"TestSite{n}")
    domain = factory.LazyAttribute(lambda obj: f"{obj.name.lower()}.example.com")
