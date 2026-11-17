"""The context processor the stand-in templates read the site name from."""

from __future__ import annotations

from django.http import HttpRequest

from freedom_ls.panel_framework.sites import resolve_site


def site_name(request: HttpRequest) -> dict[str, str]:
    site = resolve_site(request)
    return {"site_name": site.name if site else ""}
