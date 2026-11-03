from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

import time_machine

from django.template import Context, Template

JOHANNESBURG = ZoneInfo("Africa/Johannesburg")
DUE = datetime(2026, 3, 15, 23, 59, tzinfo=JOHANNESBURG)


def _render(**context: object) -> str:
    template = Template("{% load time_tags %}{% local_time due %}")
    return template.render(Context({"due": DUE, **context}))


def _render_with_format(format: str, due: datetime = DUE) -> str:
    template = Template("{% load time_tags %}{% local_time due format=format %}")
    return template.render(Context({"due": due, "format": format}))


def test_the_datetime_attribute_is_the_utc_instant():
    assert 'datetime="2026-03-15T21:59:00+00:00"' in _render()


def test_an_end_of_day_instant_carries_whole_seconds():
    """A deadline without a time falls due at time.max; six fraction digits are outside
    the date-time format a browser is promised to parse."""
    end_of_day = datetime.combine(DUE.date(), time.max, tzinfo=JOHANNESBURG)

    rendered = Template("{% load time_tags %}{% local_time due %}").render(
        Context({"due": end_of_day})
    )

    assert 'datetime="2026-03-15T21:59:59+00:00"' in rendered


def test_the_text_names_the_site_zone():
    assert ">15 Mar 2026, 23:59 SAST</time>" in _render()


def test_the_element_is_the_local_time_component():
    assert 'x-data="localTime"' in _render()


def test_data_show_zone_follows_the_context_flag():
    assert 'data-show-zone="true"' in _render(show_time_zone_to_learners=True)
    assert 'data-show-zone="false"' in _render(show_time_zone_to_learners=False)
    assert 'data-show-zone="false"' in _render()


def test_the_utc_instant_is_independent_of_the_zone_the_value_arrives_in():
    in_utc = DUE.astimezone(UTC)
    template = Template("{% load time_tags %}{% local_time due %}")

    rendered = template.render(Context({"due": in_utc}))

    assert 'datetime="2026-03-15T21:59:00+00:00"' in rendered


@time_machine.travel(datetime(2026, 6, 1, tzinfo=UTC), tick=False)
def test_the_short_format_marks_the_element_and_keeps_the_instant():
    rendered = _render_with_format(
        "short", datetime(2026, 1, 1, 8, tzinfo=JOHANNESBURG)
    )

    assert 'data-format="short"' in rendered
    assert 'datetime="2026-01-01T06:00:00+00:00"' in rendered
    assert 'x-data="localTime"' in rendered
    assert ">1 Jan</time>" in rendered


@time_machine.travel(datetime(2026, 6, 1, tzinfo=UTC), tick=False)
def test_the_short_format_names_the_year_when_it_is_not_this_year():
    rendered = _render_with_format(
        "short", datetime(2020, 1, 1, 8, tzinfo=JOHANNESBURG)
    )

    assert ">1 Jan 2020</time>" in rendered


def test_the_today_format_is_a_fixed_word_the_browser_leaves_alone():
    rendered = _render_with_format("today")

    assert ">Today</time>" in rendered
    assert "x-data" not in rendered
    assert 'datetime="2026-03-15T21:59:00+00:00"' in rendered


def test_the_default_format_has_no_format_attribute():
    assert "data-format" not in _render()
