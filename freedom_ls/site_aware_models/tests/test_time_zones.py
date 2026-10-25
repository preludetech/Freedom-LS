from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from django.conf import settings
from django.contrib.sites.models import Site
from django.http import HttpRequest
from django.test import RequestFactory

from freedom_ls.site_aware_models.factories import SiteTimeZoneConfigFactory
from freedom_ls.site_aware_models.models import _thread_locals
from freedom_ls.site_aware_models.time_zones import (
    shows_time_zone_to_learners,
    site_time_zone,
    site_time_zone_config,
    site_zone_text,
)


@contextmanager
def ambient_request(request: HttpRequest) -> Iterator[None]:
    """Make `request` the one the middleware would have set, in place of the test site
    context's mock, which the cache deliberately ignores."""
    previous = _thread_locals.request
    _thread_locals.request = request
    try:
        yield
    finally:
        _thread_locals.request = previous


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


@pytest.mark.django_db
def test_a_request_reads_the_row_once(
    mock_site_context: Site, django_assert_num_queries
) -> None:
    """One page resolves deadlines, labels dates and renders admin rows, each asking for the
    zone; the row is read once per request rather than once per asker."""
    SiteTimeZoneConfigFactory(time_zone="Africa/Johannesburg")
    request = RequestFactory().get("/")
    with ambient_request(request), django_assert_num_queries(1):
        site_time_zone(mock_site_context)
        shows_time_zone_to_learners(mock_site_context)
        site_time_zone_config(mock_site_context)


@pytest.mark.django_db
def test_a_new_request_reads_the_row_again(mock_site_context: Site) -> None:
    with ambient_request(RequestFactory().get("/")):
        assert site_time_zone(mock_site_context) == ZoneInfo(settings.TIME_ZONE)
    SiteTimeZoneConfigFactory(time_zone="Africa/Johannesburg")

    with ambient_request(RequestFactory().get("/")):
        assert site_time_zone(mock_site_context) == ZoneInfo("Africa/Johannesburg")


@pytest.mark.django_db
def test_the_cache_is_per_site(mock_site_context: Site) -> None:
    other_site = Site.objects.create(name="Other", domain="other.example.com")
    SiteTimeZoneConfigFactory(site=other_site, time_zone="Asia/Tokyo")

    with ambient_request(RequestFactory().get("/")):
        assert site_time_zone(mock_site_context) == ZoneInfo(settings.TIME_ZONE)
        assert site_time_zone(other_site) == ZoneInfo("Asia/Tokyo")


def test_site_zone_text_names_the_zone() -> None:
    instant = datetime(2026, 3, 14, 17, 0, tzinfo=ZoneInfo("Africa/Johannesburg"))

    assert site_zone_text(instant) == "14 Mar 2026, 17:00 SAST"
