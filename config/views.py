"""Project-level views for site-wide concerns (robots.txt, etc.)."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.urls import reverse


def robots_txt(request: HttpRequest) -> HttpResponse:
    """Serve a dynamic robots.txt that allows the public course pages.

    References this site's sitemap via an absolute URL so the Sitemap line
    is multi-tenant correct (each site gets its own domain).
    """
    sitemap_url = request.build_absolute_uri(reverse("sitemap"))
    content = f"User-agent: *\nAllow: /courses/\n\nSitemap: {sitemap_url}\n"
    return HttpResponse(content, content_type="text/plain")
