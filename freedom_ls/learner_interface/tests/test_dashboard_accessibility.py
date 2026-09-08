"""Accessibility contract for the dashboard's paginated sections.

Focus movement itself is JavaScript and is exercised in the browser, not here.
What these pin is the markup that focus movement depends on: a control that
never disappears, a heading outside the swap, and one live region.
"""

from __future__ import annotations

import re

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.content_engine.factories import CourseCategoryFactory, CourseFactory


@pytest.fixture
def four_available_courses(mock_site_context) -> list:
    return [
        CourseFactory(title=f"Course {letter}", slug=f"course-{letter.lower()}")
        for letter in ["A", "B", "C", "D"]
    ]


def _dashboard_body(**headers: str) -> str:
    response = Client().get(reverse("learner_interface:dashboard"), **headers)
    return response.content.decode()


@pytest.mark.django_db
def test_both_controls_render_with_previous_disabled_on_page_one(
    four_available_courses,
):
    body = _dashboard_body()

    assert body.count('data-direction="previous"') == 1
    assert body.count('data-direction="next"') == 1
    assert re.search(
        r'aria-disabled="true"[^>]*data-direction="previous"', body, re.S
    ) or re.search(r'data-direction="previous"[^>]*aria-disabled="true"', body, re.S)


@pytest.mark.django_db
def test_the_next_control_is_disabled_on_the_last_page(four_available_courses):
    response = Client().get(
        reverse("learner_interface:dashboard"), {"page_available": "2"}
    )
    body = response.content.decode()

    assert body.count('data-direction="next"') == 1
    assert re.search(
        r'data-direction="next"[^>]*aria-disabled="true"', body, re.S
    ) or re.search(r'aria-disabled="true"[^>]*data-direction="next"', body, re.S)


@pytest.mark.django_db
def test_a_disabled_control_never_uses_the_disabled_attribute(four_available_courses):
    """`disabled` would take the control out of the tab order, so focus could
    not return to the control the learner just pressed."""
    body = _dashboard_body()

    assert "disabled>" not in body
    assert 'aria-disabled="true"' in body


@pytest.mark.django_db
def test_each_section_nav_carries_a_unique_label(mock_site_context):
    category = CourseCategoryFactory(title="Start here", slug="start-here")
    CourseFactory(title="Course A", slug="course-a", dashboard_category=category)
    CourseFactory(title="Course B", slug="course-b")

    body = _dashboard_body()

    labels = re.findall(r'<nav aria-label="([^"]+) pages"', body)
    assert sorted(labels) == ["Available courses", "Start here"]


@pytest.mark.django_db
def test_the_heading_sits_outside_the_swapped_element(four_available_courses):
    body = _dashboard_body()

    heading_position = body.index('id="section-heading-available"')
    swap_position = body.index('id="section-page-available"')
    assert heading_position < swap_position


@pytest.mark.django_db
def test_the_heading_can_take_focus(four_available_courses):
    body = _dashboard_body()

    assert re.search(r'id="section-heading-available"\s+tabindex="-1"', body)


@pytest.mark.django_db
def test_the_page_carries_exactly_one_status_region(mock_site_context):
    CourseCategoryFactory(title="Start here", slug="start-here")
    CourseFactory(
        title="Course A",
        slug="course-a",
        dashboard_category=CourseCategoryFactory(title="Assessment", slug="assessment"),
    )
    CourseFactory(title="Course B", slug="course-b")

    body = _dashboard_body()

    assert body.count('id="dashboard-section-status"') == 1
    # The toast container carries the page's other role="status", so the
    # dashboard's own region is identified by aria-atomic.
    assert body.count('aria-atomic="true"') == 1


@pytest.mark.django_db
def test_the_whole_page_status_region_starts_empty_and_out_of_band_free(
    four_available_courses,
):
    body = _dashboard_body()

    assert 'id="dashboard-section-status"' in body
    assert "hx-swap-oob" not in body


@pytest.mark.django_db
def test_the_htmx_fragment_updates_the_status_region_out_of_band(
    four_available_courses,
):
    body = _dashboard_body(
        HTTP_HX_REQUEST="true", HTTP_HX_TARGET="section-page-available"
    )

    assert 'id="dashboard-section-status"' in body
    assert 'hx-swap-oob="true"' in body
    assert "Available courses: showing 1 to 3 of 4" in body
