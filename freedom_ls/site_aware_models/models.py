from __future__ import annotations

import uuid
from threading import local

from django.contrib.sites.models import Site
from django.contrib.sites.requests import RequestSite
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import DisallowedHost
from django.db import models
from django.http import HttpRequest

from .config import config

_thread_locals = local()

_CACHED_SITE_ATTR = "_cached_site"


class UnknownSite(RequestSite):
    """The site of a request whose Host header Django has already rejected.

    Deliberately not a `Site`: callers that need a real row check
    `isinstance(site, Site)` and fall back to their own default rather than
    query against this.
    """

    def __init__(self) -> None:
        self.domain = self.name = ""


def get_cached_site(request: HttpRequest) -> Site | RequestSite:
    """Get the current site, cached on the request for performance."""
    cached: Site | RequestSite | None = getattr(request, _CACHED_SITE_ATTR, None)
    if cached is not None:
        return cached

    force_name = config.FORCE_SITE_NAME
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
        try:
            site = get_current_site(request)
        except DisallowedHost:
            # A host outside ALLOWED_HOSTS resolves to no site at all, and the
            # only thing that renders such a request is Django's 400 handler.
            # That handler builds a full RequestContext, so every context
            # processor runs -- including the two that land here -- and raising
            # would turn the 400 into a 500 plus an error mail for every bot
            # that reaches the server by address.
            site = UnknownSite()

    setattr(request, _CACHED_SITE_ATTR, site)
    return site


class SiteAwareManager(models.Manager):
    def get_queryset(self):
        queryset = super().get_queryset()
        request = getattr(_thread_locals, "request", None)
        if request:
            site = get_cached_site(request)
            # A rejected Host resolves to UnknownSite, which is not a row and
            # cannot be filtered against. Fall through unfiltered rather than
            # raise: the only thing that renders such a request is the 400 page.
            if isinstance(site, Site):
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
                site = get_cached_site(request)
                # UnknownSite is not a row, and assigning it raises ValueError
                # from the descriptor. Leaving site unset instead lets the save
                # fail on the plain "this field cannot be null" path.
                if isinstance(site, Site):
                    self.site = site


class SiteAwareModel(SiteAwareModelBase):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimestampedModel(models.Model):
    """Adds creation and modification timestamps.

    Composed alongside whichever base a model already uses, rather than folded
    into SiteAwareModel, so it also reaches accounts.User (SiteAwareModelBase
    only) and models that are deliberately not site-aware.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
