from __future__ import annotations

import uuid
from threading import local

from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.sites.requests import RequestSite
from django.contrib.sites.shortcuts import get_current_site
from django.db import models
from django.http import HttpRequest

_thread_locals = local()

_CACHED_SITE_ATTR = "_cached_site"


def get_cached_site(request: HttpRequest) -> Site | RequestSite:
    """Get the current site, cached on the request for performance."""
    cached: Site | RequestSite | None = getattr(request, _CACHED_SITE_ATTR, None)
    if cached is not None:
        return cached

    force_name = getattr(settings, "FORCE_SITE_NAME", None)
    site: Site | RequestSite
    if force_name:
        try:
            site = Site.objects.get(name=force_name)
        except Site.DoesNotExist as err:
            available = list(Site.objects.values_list("name", flat=True))
            raise Site.DoesNotExist(
                f"FORCE_SITE_NAME={force_name!r} does not match any Site. "
                f"Available sites: {available}"
            ) from err
    else:
        site = get_current_site(request)

    setattr(request, _CACHED_SITE_ATTR, site)
    return site


class SiteAwareManager(models.Manager):
    def get_queryset(self):
        queryset = super().get_queryset()
        request = getattr(_thread_locals, "request", None)
        if request:
            site = get_cached_site(request)
            return queryset.filter(site=site)
        return queryset


class SiteAwareModelBase(models.Model):
    site = models.ForeignKey(Site, on_delete=models.PROTECT)

    objects: models.Manager = SiteAwareManager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self._set_site_from_request()
        super().save(*args, **kwargs)

    def full_clean(self, *args, **kwargs):
        self._set_site_from_request()
        super().full_clean(*args, **kwargs)

    def _set_site_from_request(self) -> None:
        """Automatically set site from the current request if not already set."""
        if not self.site_id:
            request = getattr(_thread_locals, "request", None)
            if request:
                # In practice, get_cached_site always returns Site when
                # django.contrib.sites is installed (which it always is).
                self.site = get_cached_site(request)  # type: ignore[assignment]


class SiteAwareModel(SiteAwareModelBase):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True
