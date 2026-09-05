from __future__ import annotations

import uuid
from threading import local

from django.contrib.sites.models import Site
from django.contrib.sites.requests import RequestSite
from django.contrib.sites.shortcuts import get_current_site
from django.db import models
from django.http import HttpRequest

from .config import config

_thread_locals = local()

_CACHED_SITE_ATTR = "_cached_site"


def get_cached_site(request: HttpRequest | None) -> Site | RequestSite:
    """Get the current site, cached on the request for performance.

    The request is optional because outbound email is not always sent from one.
    Without a request there is nothing to cache on and no host to resolve, so
    only FORCE_SITE_NAME can answer; anything else falls through to Django's own
    resolution and its own error.
    """
    if request is not None:
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
        site = get_current_site(request)

    if request is not None:
        setattr(request, _CACHED_SITE_ATTR, site)
    return site


def site_display_name(site: Site | RequestSite | int) -> str:
    """The tenant's own display name: HEADER_TITLE, else the Site row's own name.

    The one answer to "what is this installation called", shared by the site
    header, outbound email and the cohort reports, so a project that renamed
    itself in one place is not still called something else in another.

    A pk is resolved to its row only when HEADER_TITLE is unset, so a configured
    installation pays no query for a name it never reads.
    """
    header_title = config.HEADER_TITLE
    if header_title:
        return header_title
    if isinstance(site, int):
        site = Site.objects.get(pk=site)
    return site.name


def site_display_name_for_request(request: HttpRequest | None) -> str:
    """The display name for a caller holding only a request.

    HEADER_TITLE answers on its own, so the site is resolved only when the name
    has to come from the Site row. Outbound mail is not always sent from a
    request, and without one there is no host to resolve -- an installation that
    has already said what it is called should not need one to name itself.
    """
    header_title = config.HEADER_TITLE
    if header_title:
        return header_title
    return site_display_name(get_cached_site(request))


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
