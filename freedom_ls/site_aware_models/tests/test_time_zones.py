from zoneinfo import ZoneInfo

import pytest

from django.conf import settings
from django.contrib.sites.models import Site

from freedom_ls.site_aware_models.factories import SiteTimeZoneConfigFactory
from freedom_ls.site_aware_models.time_zones import (
    shows_time_zone_to_learners,
    site_time_zone,
    site_time_zone_config,
)


@pytest.mark.django_db
def test_no_row_falls_back_to_settings_time_zone_and_no_label(
    mock_site_context: Site,
) -> None:
    assert site_time_zone_config(mock_site_context) is None
    assert site_time_zone(mock_site_context) == ZoneInfo(settings.TIME_ZONE)
    assert shows_time_zone_to_learners(mock_site_context) is False


@pytest.mark.django_db
def test_row_drives_the_zone_and_the_label_flag(mock_site_context: Site) -> None:
    SiteTimeZoneConfigFactory(
        time_zone="Africa/Johannesburg", show_time_zone_to_learners=True
    )

    assert site_time_zone(mock_site_context) == ZoneInfo("Africa/Johannesburg")
    assert shows_time_zone_to_learners(mock_site_context) is True


@pytest.mark.django_db
def test_another_sites_row_does_not_apply(mock_site_context: Site) -> None:
    other_site = Site.objects.create(name="Other", domain="other.example.com")
    SiteTimeZoneConfigFactory(
        site=other_site, time_zone="Asia/Tokyo", show_time_zone_to_learners=True
    )

    assert site_time_zone(mock_site_context) == ZoneInfo(settings.TIME_ZONE)
    assert shows_time_zone_to_learners(mock_site_context) is False
    assert site_time_zone(other_site) == ZoneInfo("Asia/Tokyo")
