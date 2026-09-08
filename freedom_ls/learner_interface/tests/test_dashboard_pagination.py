"""Per-section paging on the dashboard: page state, clamping and the htmx branch.

Page state is one namespaced query parameter per section, ``page_<slug>``,
written only when that section is off page one.
"""

from __future__ import annotations

import pytest

from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseCategoryFactory, CourseFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.course_recommendations.factories import RecommendedCourseFactory
from freedom_ls.learner_interface.dashboard_sections import section_page_href
from freedom_ls.learner_management.factories import (
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)

from .conftest import rendered_section

DASHBOARD_URL = "/"


@pytest.fixture
def four_available_courses(mock_site_context) -> list:
    return [
        CourseFactory(title=f"Course {letter}", slug=f"course-{letter.lower()}")
        for letter in ["A", "B", "C", "D"]
    ]


@pytest.mark.django_db
def test_page_one_renders_three_and_reports_the_position(four_available_courses):
    response = Client().get(reverse("learner_interface:dashboard"))

    available = rendered_section(response, "available")
    assert available.courses == four_available_courses[:3]
    assert available.position_text == "1 to 3 of 4"


@pytest.mark.django_db
def test_page_two_renders_the_fourth_course(four_available_courses):
    response = Client().get(
        reverse("learner_interface:dashboard"), {"page_available": "2"}
    )

    available = rendered_section(response, "available")
    assert available.courses == [four_available_courses[3]]
    assert available.position_text == "4 to 4 of 4"


@pytest.mark.django_db
@pytest.mark.parametrize("page_value", ["abc", "0", "-1", "9999"])
def test_a_bad_page_number_clamps_and_returns_200(four_available_courses, page_value):
    response = Client().get(
        reverse("learner_interface:dashboard"), {"page_available": page_value}
    )

    assert response.status_code == 200
    assert rendered_section(response, "available").courses


@pytest.mark.django_db
def test_an_unrecognised_page_parameter_is_ignored(four_available_courses):
    response = Client().get(
        reverse("learner_interface:dashboard"), {"page_no_such_section": "3"}
    )

    assert response.status_code == 200
    assert rendered_section(response, "available").courses == four_available_courses[:3]


@pytest.mark.django_db
def test_recommended_courses_page_like_the_rest(mock_site_context, logged_in_client):
    """Recommended is the one section whose rows are RecommendedCourse objects
    rather than courses, so a shared helper is most likely to miss it."""
    user = UserFactory()
    recommended = [
        CourseFactory(title=f"Course {letter}", slug=f"course-{letter.lower()}")
        for letter in ["A", "B", "C", "D"]
    ]
    for course in recommended:
        RecommendedCourseFactory(user=user, course=course)
    client = logged_in_client(user)

    first_page = client.get(reverse("learner_interface:dashboard"))
    second_page = client.get(
        reverse("learner_interface:dashboard"), {"page_recommended": "2"}
    )

    assert len(rendered_section(first_page, "recommended").courses) == 3
    assert rendered_section(first_page, "recommended").position_text == "1 to 3 of 4"
    assert len(rendered_section(second_page, "recommended").courses) == 1


@pytest.mark.django_db
def test_in_progress_pages(mock_site_context, logged_in_client):
    user = UserFactory()
    learner = LearnerFactory(user=user)
    for letter in ["A", "B", "C", "D"]:
        course = CourseFactory(
            title=f"Course {letter}", slug=f"course-{letter.lower()}"
        )
        LearnerCourseRegistrationFactory(learner=learner, course=course)
    client = logged_in_client(user)

    response = client.get(reverse("learner_interface:dashboard"))

    in_progress = rendered_section(response, "in-progress")
    assert len(in_progress.courses) == 3
    assert in_progress.position_text == "1 to 3 of 4"


# --- link building ---


@pytest.mark.django_db
def test_a_link_preserves_every_other_sections_page(rf):
    request = rf.get(DASHBOARD_URL, {"page_available": "2", "page_history": "3"})

    href = section_page_href(request, "page_available", 3)

    assert "page_available=3" in href
    assert "page_history=3" in href


@pytest.mark.django_db
def test_a_page_one_link_drops_its_own_parameter(rf):
    request = rf.get(DASHBOARD_URL, {"page_available": "2", "page_history": "3"})

    href = section_page_href(request, "page_available", 1)

    assert "page_available" not in href
    assert "page_history=3" in href


@pytest.mark.django_db
def test_a_link_carries_an_unrecognised_parameter_through(rf):
    request = rf.get(DASHBOARD_URL, {"utm_source": "newsletter"})

    href = section_page_href(request, "page_available", 2)

    assert "utm_source=newsletter" in href
    assert "page_available=2" in href


@pytest.mark.django_db
def test_a_page_one_link_with_nothing_else_is_the_bare_path(rf):
    request = rf.get(DASHBOARD_URL)

    assert section_page_href(request, "page_available", 1) == DASHBOARD_URL


# --- the htmx branch ---


@pytest.mark.django_db
def test_an_htmx_request_returns_one_section_rather_than_the_page(
    four_available_courses,
):
    response = Client().get(
        reverse("learner_interface:dashboard"),
        HTTP_HX_REQUEST="true",
        HTTP_HX_TARGET="section-page-available",
    )
    body = response.content.decode()

    assert response.status_code == 200
    assert "<h1" not in body
    assert 'id="section-page-available"' in body
    assert four_available_courses[0].title in body


@pytest.mark.django_db
def test_the_same_url_without_the_htmx_header_returns_the_whole_page(
    four_available_courses,
):
    response = Client().get(reverse("learner_interface:dashboard"))

    assert "<h1" in response.content.decode()


@pytest.mark.django_db
def test_an_htmx_request_for_a_category_returns_that_category(mock_site_context):
    category = CourseCategoryFactory(title="Start here", slug="start-here")
    course: Course = CourseFactory(
        title="Course A", slug="course-a", dashboard_category=category
    )

    response = Client().get(
        reverse("learner_interface:dashboard"),
        HTTP_HX_REQUEST="true",
        HTTP_HX_TARGET="section-page-start-here",
    )

    assert response.status_code == 200
    assert course.title in response.content.decode()


@pytest.mark.django_db
def test_an_htmx_request_with_no_target_header_is_a_404(four_available_courses):
    response = Client().get(
        reverse("learner_interface:dashboard"), HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_an_htmx_request_for_an_unknown_section_is_a_404(four_available_courses):
    response = Client().get(
        reverse("learner_interface:dashboard"),
        HTTP_HX_REQUEST="true",
        HTTP_HX_TARGET="section-page-no-such-thing",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_an_anonymous_htmx_request_for_in_progress_is_a_404(four_available_courses):
    response = Client().get(
        reverse("learner_interface:dashboard"),
        HTTP_HX_REQUEST="true",
        HTTP_HX_TARGET="section-page-in-progress",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_an_htmx_request_for_an_empty_section_is_a_404(mock_site_context):
    response = Client().get(
        reverse("learner_interface:dashboard"),
        HTTP_HX_REQUEST="true",
        HTTP_HX_TARGET="section-page-available",
    )

    assert response.status_code == 404
