"""Tests for the all_courses view at the context level.

These exercise the status/annotation logic the view attaches to each course
object it puts in the ``all_courses`` context: listing_status, progress
percentage, accent slot, and the absence of next_up_*
annotations. Rendered-HTML row assertions live in ``test_all_courses_rows``.
"""

from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory

# --- access + base annotations ---


@pytest.mark.django_db
def test_all_courses_started_course_has_progress_percentage(
    mock_site_context, courses, logged_in_client
):
    """Started courses in the all_courses view should have progress_percentage for progress bars."""
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=courses[0])
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:courses"))
    assert response.status_code == 200

    all_courses_list = list(response.context["all_courses"])
    started_course = next(c for c in all_courses_list if c.id == courses[0].id)
    # Real-value assertion: a freshly-registered course with no topic
    # completion has a progress percentage of 0. `hasattr` only proved the
    # attribute existed; this proves the annotation produced the right value.
    assert started_course.progress_percentage == 0


@pytest.mark.django_db
def test_all_courses_annotates_accent_slot_key(
    mock_site_context, courses, logged_in_client
):
    """Every course returned to the all_courses page has an ``accent_slot_key``."""
    user = UserFactory()
    client = logged_in_client(user)
    response = client.get(reverse("learner_interface:courses"))
    assert response.status_code == 200
    from freedom_ls.content_engine.course_accent import PALETTE

    all_courses_list = list(response.context["all_courses"])
    assert all_courses_list, "Expected at least one course in the catalogue"
    assert all(c.accent_slot_key in PALETTE for c in all_courses_list)
