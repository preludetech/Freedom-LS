"""Tests for ``Course.accent_slot`` assignment and the ``accent_role`` property."""

from __future__ import annotations

from collections import Counter

import pytest

from django.contrib.sites.models import Site

from freedom_ls.content_engine.course_accent import PALETTE
from freedom_ls.content_engine.factories import CourseFactory


@pytest.mark.django_db
def test_first_course_gets_slot_zero(mock_site_context):
    course = CourseFactory()
    assert course.accent_slot == 0


@pytest.mark.django_db
def test_slots_cycle_through_palette(mock_site_context):
    courses = [CourseFactory() for _ in range(6)]
    assert [c.accent_slot for c in courses] == [0, 1, 2, 3, 4, 0]


@pytest.mark.django_db
def test_ten_courses_are_evenly_distributed(mock_site_context):
    courses = [CourseFactory() for _ in range(10)]
    counts = Counter(c.accent_slot for c in courses)
    assert counts == {0: 2, 1: 2, 2: 2, 3: 2, 4: 2}


@pytest.mark.django_db
def test_accent_role_property_returns_palette_entry(mock_site_context):
    course = CourseFactory()
    assert course.accent_role == PALETTE[course.accent_slot]


@pytest.mark.django_db
def test_per_site_slots_are_independent():
    """Two sites both start their cycle at slot 0; counts don't bleed across sites."""
    site_a, _ = Site.objects.get_or_create(name="SiteA", defaults={"domain": "a"})
    site_b, _ = Site.objects.get_or_create(name="SiteB", defaults={"domain": "b"})

    a_courses = [CourseFactory(site=site_a) for _ in range(3)]
    b_courses = [CourseFactory(site=site_b) for _ in range(2)]

    assert [c.accent_slot for c in a_courses] == [0, 1, 2]
    assert [c.accent_slot for c in b_courses] == [0, 1]


@pytest.mark.django_db
def test_update_does_not_reshuffle_slot(mock_site_context):
    course = CourseFactory()
    original = course.accent_slot
    # Create more courses; saving the first one again should not change its slot.
    CourseFactory()
    CourseFactory()
    course.title = "Updated title"
    course.save()
    course.refresh_from_db()
    assert course.accent_slot == original
