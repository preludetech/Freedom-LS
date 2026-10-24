from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.sites.models import Site

from freedom_ls.site_aware_models.models import SiteTimeZoneConfig


def site_time_zone_config(site: Site) -> SiteTimeZoneConfig | None:
    """The site's row, or None. Reads through _base_manager so a task with no request still
    resolves the right site's zone."""
    return SiteTimeZoneConfig._base_manager.filter(site=site).first()


def site_time_zone(site: Site) -> ZoneInfo:
    row = site_time_zone_config(site)
    return ZoneInfo(row.time_zone if row is not None else settings.TIME_ZONE)


def shows_time_zone_to_learners(site: Site) -> bool:
    row = site_time_zone_config(site)
    return row.show_time_zone_to_learners if row is not None else False
