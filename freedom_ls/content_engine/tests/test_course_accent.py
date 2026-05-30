"""Tests for the per-course accent palette.

Covers the ``PALETTE`` contract (pure) and the stored ``accent_slot``
assignment / ``accent_role`` property on ``Course`` (DB-backed).
"""

from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import SiteFactory
from freedom_ls.content_engine.course_accent import PALETTE
from freedom_ls.content_engine.factories import CourseFactory

# --- PALETTE contract (pure) ---


def test_palette_has_five_entries() -> None:
    assert len(PALETTE) == 5


def test_palette_is_decoupled_from_ui_role_names() -> None:
    """Card accents are a separate themeable series, not the UI role tokens.

    Guards the design contract: the slot keys must not be semantic role
    names, so recolouring cards never recolours buttons/badges.
    """
    ui_roles = {"primary", "secondary", "accent", "info", "success", "error", "warning"}
    assert not (set(PALETTE) & ui_roles)


# --- accent_slot assignment & accent_role property (DB-backed) ---


@pytest.mark.django_db
def test_slots_cycle_through_palette_in_creation_order(mock_site_context):
    """Per-site creation order cycles 0→1→2→3→4→0, keeping the catalogue even."""
    courses = [CourseFactory() for _ in range(6)]
    assert [c.accent_slot for c in courses] == [0, 1, 2, 3, 4, 0]


@pytest.mark.django_db
def test_accent_role_maps_slots_to_palette_entries(mock_site_context):
    """The first two courses (slots 0, 1) expose the first two palette keys."""
    first, second = CourseFactory(), CourseFactory()
    assert (first.accent_role, second.accent_role) == ("1", "2")


@pytest.mark.django_db
def test_slots_are_assigned_per_site_independently():
    site_a = SiteFactory(name="SiteA", domain="a.example.com")
    site_b = SiteFactory(name="SiteB", domain="b.example.com")

    a_courses = [CourseFactory(site=site_a) for _ in range(3)]
    b_courses = [CourseFactory(site=site_b) for _ in range(2)]

    assert [c.accent_slot for c in a_courses] == [0, 1, 2]
    assert [c.accent_slot for c in b_courses] == [0, 1]


@pytest.mark.django_db
def test_updating_a_course_does_not_reshuffle_its_slot(mock_site_context):
    course = CourseFactory()
    original = course.accent_slot
    # Adding more courses then re-saving the first must not change its slot.
    CourseFactory()
    CourseFactory()

    course.title = "Updated title"
    course.save()
    course.refresh_from_db()

    assert course.accent_slot == original
