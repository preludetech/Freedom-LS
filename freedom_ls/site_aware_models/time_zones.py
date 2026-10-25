from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.sites.models import Site
from django.http import HttpRequest

from freedom_ls.site_aware_models.models import SiteTimeZoneConfig, _thread_locals

_CACHED_CONFIGS_ATTR = "_site_time_zone_configs"


def site_time_zone_config(site: Site) -> SiteTimeZoneConfig | None:
    """The site's row, or None. Reads through _base_manager so a task with no request still
    resolves the right site's zone.

    Cached on the current request, as get_cached_site caches the site: a page resolves
    deadlines, labels dates and renders admin rows, each of which asks for the zone. Only a
    real request caches; a management command or the test site context reads fresh."""
    request = getattr(_thread_locals, "request", None)
    if not isinstance(request, HttpRequest):
        return SiteTimeZoneConfig._base_manager.filter(site=site).first()
    cached: dict[int, SiteTimeZoneConfig | None] | None = getattr(
        request, _CACHED_CONFIGS_ATTR, None
    )
    if cached is None:
        cached = {}
        setattr(request, _CACHED_CONFIGS_ATTR, cached)
    if site.pk not in cached:
        cached[site.pk] = SiteTimeZoneConfig._base_manager.filter(site=site).first()
    return cached[site.pk]


def site_time_zone(site: Site) -> ZoneInfo:
    row = site_time_zone_config(site)
    return ZoneInfo(row.time_zone if row is not None else settings.TIME_ZONE)


def shows_time_zone_to_learners(site: Site) -> bool:
    row = site_time_zone_config(site)
    return row.show_time_zone_to_learners if row is not None else False


def site_zone_text(instant: datetime) -> str:
    """An instant written in the site zone with the zone named, as the admin shows it and as
    the learner pages show it before the browser rewrites it."""
    return f"{instant:%-d %b %Y, %H:%M} {instant.tzname()}"
