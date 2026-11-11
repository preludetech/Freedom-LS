"""Tests for the <c-date /> and <c-datetime /> cotton components."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from django_cotton.compiler_regex import CottonCompiler

from django.template import Context, Template
from django.utils import timezone

_cotton_compiler = CottonCompiler()
JOHANNESBURG = ZoneInfo("Africa/Johannesburg")


def _render(template_string: str, **context: object) -> str:
    with timezone.override(JOHANNESBURG):
        return Template(_cotton_compiler.process(template_string)).render(
            Context(context)
        )


def test_date_renders_the_display_format_in_a_time_element() -> None:
    result = _render('<c-date :value="when" />', when=date(2026, 11, 3))

    assert '<time datetime="2026-11-03">3 Nov 2026</time>' in result


def test_date_of_a_datetime_is_the_date_in_the_current_zone() -> None:
    instant = datetime(2026, 11, 3, 23, 30, tzinfo=ZoneInfo("UTC"))

    result = _render('<c-date :value="when" />', when=instant)

    assert ">4 Nov 2026</time>" in result


def test_date_without_a_value_renders_a_dash() -> None:
    assert _render('<c-date :value="when" />', when=None).strip() == "-"


def test_datetime_splits_date_and_time_so_a_narrow_cell_wraps_between_them() -> None:
    instant = datetime(2026, 11, 3, 7, 37, tzinfo=JOHANNESBURG)

    result = _render('<c-datetime :value="when" />', when=instant)

    assert 'datetime="2026-11-03T07:37:00+02:00"' in result
    assert '<span class="whitespace-nowrap">3 Nov 2026,</span>' in result
    assert '<span class="whitespace-nowrap">07:37</span>' in result


def test_datetime_without_a_value_renders_a_dash() -> None:
    assert _render('<c-datetime :value="when" />', when=None).strip() == "-"
