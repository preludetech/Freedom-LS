"""Base factory for site-aware models."""

import factory

from django.contrib.sites.models import Site
from django.db import models as django_models

from freedom_ls.site_aware_models.models import _thread_locals


def _get_current_site() -> Site | None:
    """Get the current site from the thread-local request context."""
    from django.contrib.sites.shortcuts import get_current_site

    request = getattr(_thread_locals, "request", None)
    if request:
        return get_current_site(request)
    return None


class SiteAwareFactory(factory.django.DjangoModelFactory):
    """Base factory for all SiteAwareModel subclasses.

    Automatically sets the site from the thread-local request context
    (set up by the ``mock_site_context`` fixture in tests).

    Overrides ``_create`` to instantiate and save directly, bypassing
    custom site-aware managers that would fail with mock requests.
    """

    site = factory.LazyFunction(_get_current_site)

    class Meta:
        abstract = True

    @classmethod
    def _create(
        cls,
        model_class: type[django_models.Model],
        *args: object,
        **kwargs: object,
    ) -> django_models.Model:
        """Instantiate and save directly, bypassing custom managers."""
        obj = model_class(*args, **kwargs)
        obj.save()
        return obj
