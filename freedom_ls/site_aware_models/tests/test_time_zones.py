from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import pytest
import time_machine

from django.conf import settings
from django.contrib.sites.models import Site
from django.http import HttpRequest
from django.test import RequestFactory

from freedom_ls.site_aware_models.factories import SiteTimeZoneConfigFactory
from freedom_ls.site_aware_models.models import _thread_locals
from freedom_ls.site_aware_models.time_zones import (
    has_set_time,
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
    """One page can ask for the zone many times; the row is read once per request rather
    than once per asker."""
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


def test_site_zone_text_writes_a_single_digit_day_without_a_zero() -> None:
    instant = datetime(2026, 3, 4, 17, 0, tzinfo=ZoneInfo("Africa/Johannesburg"))

    assert site_zone_text(instant) == "4 Mar 2026, 17:00 SAST"


JOHANNESBURG = ZoneInfo("Africa/Johannesburg")


def _end_of_day(day: date) -> datetime:
    """An instant that stands for a date alone."""
    return datetime.combine(day, time.max, tzinfo=JOHANNESBURG)


def test_a_date_only_instant_has_no_set_time() -> None:
    assert has_set_time(_end_of_day(date(2026, 1, 1))) is False
    assert has_set_time(datetime(2026, 1, 1, 23, 59, tzinfo=JOHANNESBURG)) is True


@time_machine.travel(datetime(2026, 6, 1, tzinfo=UTC), tick=False)
def test_short_site_zone_text_omits_the_year_in_the_current_year() -> None:
    assert site_zone_text(_end_of_day(date(2026, 1, 1)), short=True) == "1 Jan"


@time_machine.travel(datetime(2026, 6, 1, tzinfo=UTC), tick=False)
def test_short_site_zone_text_names_the_year_otherwise() -> None:
    assert site_zone_text(_end_of_day(date(2020, 1, 1)), short=True) == "1 Jan 2020"


@time_machine.travel(datetime(2026, 12, 31, 23, 0, tzinfo=UTC), tick=False)
def test_short_site_zone_text_judges_the_year_in_the_instants_own_zone() -> None:
    """It is already 1 Jan 2027 in Johannesburg, so a 2027 instant there is this year."""
    assert site_zone_text(_end_of_day(date(2027, 1, 5)), short=True) == "5 Jan"


@time_machine.travel(datetime(2026, 3, 15, 8, tzinfo=UTC), tick=False)
def test_short_site_zone_text_reads_today_on_the_instants_own_date() -> None:
    assert site_zone_text(_end_of_day(date(2026, 3, 15)), short=True) == "Today"


@time_machine.travel(datetime(2026, 3, 15, 22, 30, tzinfo=UTC), tick=False)
def test_short_site_zone_text_judges_today_in_the_instants_own_zone() -> None:
    """It is already 16 Mar in Johannesburg, so a 15 Mar instant there is not today."""
    assert site_zone_text(_end_of_day(date(2026, 3, 15)), short=True) == "15 Mar"


@time_machine.travel(datetime(2026, 6, 1, tzinfo=UTC), tick=False)
def test_short_site_zone_text_adds_a_set_time_with_the_zone() -> None:
    instant = datetime(2026, 1, 1, 9, 0, tzinfo=JOHANNESBURG)

    assert site_zone_text(instant, short=True) == "1 Jan, 09:00 SAST"


@time_machine.travel(datetime(2026, 3, 15, 5, tzinfo=UTC), tick=False)
def test_short_site_zone_text_due_today_at_a_set_time() -> None:
    instant = datetime(2026, 3, 15, 9, 0, tzinfo=JOHANNESBURG)

    assert site_zone_text(instant, short=True) == "Today, 09:00 SAST"


def test_long_site_zone_text_is_unchanged_by_the_short_option() -> None:
    instant = datetime(2026, 3, 15, 23, 59, tzinfo=ZoneInfo("Africa/Johannesburg"))

    assert site_zone_text(instant) == "15 Mar 2026, 23:59 SAST"
