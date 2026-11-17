"""The site a request belongs to, as the host project resolves it."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from django.utils.module_loading import import_string

from freedom_ls.panel_framework.config import config

SETTING_NAME = "PANEL_FRAMEWORK_SITE_RESOLVER"
# The framework's own attribute, so it never aliases a cache the host keeps on the request.
_REQUEST_ATTR = "_panel_framework_site"
_UNSET = object()


def resolve_site(request: HttpRequest) -> Site | None:
    """The request's Site row, or None when the host resolves it to no row.

    Resolved once per request. The resolver is imported on the first call
    for each request rather than at module import, so a changed setting or
    a patched resolver takes effect.
    """
    cached = getattr(request, _REQUEST_ATTR, _UNSET)
    if cached is not _UNSET:
        return cast(Site | None, cached)
    try:
        resolved = _resolver()(request)
    except Site.DoesNotExist:
        # django.contrib.sites answers an unknown host this way.
        resolved = None
    site = resolved if isinstance(resolved, Site) else None
    setattr(request, _REQUEST_ATTR, site)
    return site


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
