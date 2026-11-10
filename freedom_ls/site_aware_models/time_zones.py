from datetime import datetime, time
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.sites.models import Site
from django.http import HttpRequest
from django.utils import formats, timezone

from freedom_ls.base.date_display import (
    DATE_DISPLAY_FORMAT,
    DATETIME_DISPLAY_FORMAT,
    SHORT_DATE_DISPLAY_FORMAT,
    TIME_DISPLAY_FORMAT,
)
from freedom_ls.site_aware_models.models import SiteTimeZoneConfig, _thread_locals

_CACHED_CONFIGS_ATTR = "_site_time_zone_configs"


def site_time_zone_config(site: Site) -> SiteTimeZoneConfig | None:
    """The site's row, or None. Reads through _base_manager so a task with no request still
    resolves the right site's zone.

    Cached on the current request, as get_cached_site caches the site: one page can ask for
    the zone many times. Only a real request caches; a management command or the test site
    context reads fresh."""
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


def has_set_time(instant: datetime) -> bool:
    """Whether an instant carries a time of its own. An instant that stands for a date alone
    sits at the last microsecond of its day, judged in the instant's own zone."""
    return instant.time() != time.max


def site_zone_text(instant: datetime, *, short: bool = False) -> str:
    """An instant written in the site zone with the zone named, as the admin shows it and as
    the learner pages show it before the browser rewrites it.

    The short form is the day and abbreviated month, plus the year only when it is not this
    year, judged in the instant's own zone. An instant on today's date reads "Today" instead.
    An instant with a set time adds it, with the zone named, as the long form does."""
    if not short:
        return f"{formats.date_format(instant, DATETIME_DISPLAY_FORMAT)} {instant.tzname()}"
    now = timezone.now().astimezone(instant.tzinfo)
    if instant.date() == now.date():
        text = "Today"
    elif instant.year != now.year:
        text = formats.date_format(instant, DATE_DISPLAY_FORMAT)
    else:
        text = formats.date_format(instant, SHORT_DATE_DISPLAY_FORMAT)
    if has_set_time(instant):
        text += (
            f", {formats.time_format(instant, TIME_DISPLAY_FORMAT)} {instant.tzname()}"
        )
    return text
