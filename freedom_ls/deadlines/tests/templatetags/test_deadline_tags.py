from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from django.template import Context, Template

JOHANNESBURG = ZoneInfo("Africa/Johannesburg")
DUE = datetime(2026, 3, 15, 23, 59, tzinfo=JOHANNESBURG)


def _render(**context: object) -> str:
    template = Template("{% load deadline_tags %}{% local_time due %}")
    return template.render(Context({"due": DUE, **context}))


def test_the_datetime_attribute_is_the_utc_instant():
    assert 'datetime="2026-03-15T21:59:00+00:00"' in _render()


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
    template = Template("{% load deadline_tags %}{% local_time due %}")

    rendered = template.render(Context({"due": in_utc}))

    assert 'datetime="2026-03-15T21:59:00+00:00"' in rendered
