"""Tests for Course.iso_estimated_duration() — ISO-8601 duration serialiser.

TDD: written before the method is implemented.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from freedom_ls.content_engine.factories import CourseFactory


@pytest.mark.django_db
def test_iso_estimated_duration_returns_empty_string_when_unset(mock_site_context):
    """iso_estimated_duration() returns '' when estimated_duration is None."""
    course = CourseFactory(estimated_duration=None)
    assert course.iso_estimated_duration() == ""


@pytest.mark.django_db
def test_iso_estimated_duration_returns_empty_string_for_zero(mock_site_context):
    """iso_estimated_duration() returns '' for a zero timedelta."""
    course = CourseFactory(estimated_duration=timedelta(0))
    assert course.iso_estimated_duration() == ""


@pytest.mark.django_db
def test_iso_estimated_duration_hours_only(mock_site_context):
    """iso_estimated_duration() returns 'PT2H' for exactly 2 hours."""
    course = CourseFactory(estimated_duration=timedelta(hours=2))
    assert course.iso_estimated_duration() == "PT2H"


@pytest.mark.django_db
def test_iso_estimated_duration_minutes_only(mock_site_context):
    """iso_estimated_duration() returns 'PT45M' for 45 minutes."""
    course = CourseFactory(estimated_duration=timedelta(minutes=45))
    assert course.iso_estimated_duration() == "PT45M"


@pytest.mark.django_db
def test_iso_estimated_duration_hours_and_minutes(mock_site_context):
    """iso_estimated_duration() returns 'PT1H30M' for 1 hour 30 minutes."""
    course = CourseFactory(estimated_duration=timedelta(hours=1, minutes=30))
    assert course.iso_estimated_duration() == "PT1H30M"


@pytest.mark.django_db
def test_iso_estimated_duration_large_duration(mock_site_context):
    """iso_estimated_duration() handles 3 hours 15 minutes correctly."""
    course = CourseFactory(estimated_duration=timedelta(hours=3, minutes=15))
    assert course.iso_estimated_duration() == "PT3H15M"
