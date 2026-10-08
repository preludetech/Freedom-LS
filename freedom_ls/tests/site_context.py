"""The ambient site context that site-aware code reads, as a context manager."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from unittest import mock

from django.contrib.sites.models import SITE_CACHE, Site

from freedom_ls.site_aware_models.models import _thread_locals


@contextmanager
def site_context(site: Site) -> Iterator[Site]:
    """Make `site` the ambient site for code running in this thread.

    SiteAwareModel reads the thread-local request, templates and allauth call
    get_current_site, and the role registry calls Site.objects.get_current;
    all four have to agree or a factory-built row lands on a different site
    from the one a view then reads.
    """
    had_request = hasattr(_thread_locals, "request")
    old_request = getattr(_thread_locals, "request", None) if had_request else None

    mock_request = mock.Mock()
    # A real site on the request keeps Mock objects out of ORM queries.
    mock_request._cached_site = site
    _thread_locals.request = mock_request

    SITE_CACHE.clear()
    # RequestFactory requests resolve their site by the "testserver" host.
    SITE_CACHE["testserver"] = site
    try:
        with (
            mock.patch(
                "freedom_ls.site_aware_models.models.get_current_site",
                return_value=site,
            ),
            mock.patch(
                "django.contrib.sites.shortcuts.get_current_site", return_value=site
            ),
            mock.patch(
                "django.contrib.sites.models.SiteManager.get_current",
                return_value=site,
            ),
        ):
            yield site
    finally:
        SITE_CACHE.clear()
        if had_request:
            _thread_locals.request = old_request
        elif hasattr(_thread_locals, "request"):
            delattr(_thread_locals, "request")
