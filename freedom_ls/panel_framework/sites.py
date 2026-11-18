"""The site a request belongs to, as the host project resolves it."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from django.contrib.sites.models import Site
from django.contrib.sites.requests import RequestSite
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from django.utils.module_loading import import_string

from freedom_ls.panel_framework.config import config

SETTING_NAME = "PANEL_FRAMEWORK_SITE_RESOLVER"
# The framework's own attribute, so it never aliases a cache the host keeps on the request.
_REQUEST_ATTR = "_panel_framework_site"
_UNSET = object()


def current_site_or_none(request: HttpRequest) -> Site | None:
    """The default resolver: django.contrib.sites' answer, with None for a
    host that matches no Site row, which get_current_site raises for."""
    try:
        site = get_current_site(request)
    except Site.DoesNotExist:
        return None
    return site if isinstance(site, Site) else None


def resolve_site(request: HttpRequest) -> Site | None:
    """The request's Site row, or None when the host resolves it to no row.

    The resolver says "no site" by returning None or a RequestSite; anything
    it raises propagates, so a host's own misconfiguration error is not
    mistaken for an unknown host.

    Resolved once per request. The resolver is imported on the first call
    for each request rather than at module import, so a changed setting or
    a patched resolver takes effect.
    """
    cached = getattr(request, _REQUEST_ATTR, _UNSET)
    if cached is not _UNSET:
        return cast(Site | None, cached)
    site = _as_site(_resolver()(request))
    setattr(request, _REQUEST_ATTR, site)
    return site


def _as_site(resolved: object) -> Site | None:
    """A Site row is the site. None, or a RequestSite (what django.contrib.sites
    answers when it has no row to give), is no site. Anything else is a
    resolver that answers the wrong question."""
    if isinstance(resolved, Site):
        return resolved
    if resolved is None or isinstance(resolved, RequestSite):
        return None
    raise ImproperlyConfigured(
        f"{SETTING_NAME} returned {type(resolved).__name__}, not a Site."
    )


def _resolver() -> Callable[[HttpRequest], object]:
    path = config.PANEL_FRAMEWORK_SITE_RESOLVER
    if not isinstance(path, str):
        raise ImproperlyConfigured(f"{SETTING_NAME} = {path!r} is not a dotted path.")
    try:
        resolver = import_string(path)
    except ImportError as error:
        raise ImproperlyConfigured(
            f"{SETTING_NAME} = {path!r} cannot be imported."
        ) from error
    if not callable(resolver):
        raise ImproperlyConfigured(f"{SETTING_NAME} = {path!r} is not callable.")
    return cast(Callable[[HttpRequest], object], resolver)
