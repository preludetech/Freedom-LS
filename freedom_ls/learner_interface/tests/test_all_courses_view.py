"""Tests for the all_courses view at the context level.

These exercise the status/annotation logic the view attaches to each course
object it puts in the ``all_courses`` context: listing_status, progress
percentage, accent slot, and the absence of next_up_*
annotations. Rendered-HTML row assertions live in ``test_all_courses_rows``.
"""

from __future__ import annotations

import pytest

from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.student_interface.utils import CourseListingStatus
from freedom_ls.student_management.factories import UserCourseRegistrationFactory
from freedom_ls.student_progress.factories import CourseProgressFactory

# --- access + base annotations ---


@pytest.mark.django_db
def test_all_courses_anonymous_returns_200(client, courses, mock_site_context):
    """Anonymous users can browse the catalogue — no login redirect."""
    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_all_courses_started_course_has_progress_percentage(
    mock_site_context, courses, logged_in_client
):
    """Started courses in the all_courses view should have progress_percentage for progress bars."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    client = logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
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
    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200
    from freedom_ls.content_engine.course_accent import PALETTE

    all_courses_list = list(response.context["all_courses"])
    assert all_courses_list, "Expected at least one course in the catalogue"
    assert all(c.accent_slot_key in PALETTE for c in all_courses_list)


# --- listing_status + preview context per registration state ---


@pytest.mark.django_db
def test_all_courses_not_registered_has_not_registered_status(
    mock_site_context, courses, logged_in_client
):
    """An unregistered course has listing_status=NOT_REGISTERED on the context object."""
    user = UserFactory()
    client = logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    all_courses_list = list(response.context["all_courses"])
    course = next(c for c in all_courses_list if c.id == courses[0].id)
    assert course.listing_status == CourseListingStatus.NOT_REGISTERED
    assert course.progress_percentage == 0


@pytest.mark.django_db
def test_all_courses_registered_zero_percent_has_registered_status(
    mock_site_context, courses, logged_in_client
):
    """A registered-but-not-started course has listing_status=REGISTERED and 0% progress."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    client = logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    all_courses_list = list(response.context["all_courses"])
    course = next(c for c in all_courses_list if c.id == courses[0].id)
    assert course.listing_status == CourseListingStatus.REGISTERED
    assert course.progress_percentage == 0


@pytest.mark.django_db
def test_all_courses_in_progress_has_in_progress_status(
    mock_site_context, courses, logged_in_client
):
    """A started course has listing_status=IN_PROGRESS and progress_percentage > 0."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    CourseProgressFactory(
        user=user, course=courses[0], progress_percentage=40, completed_time=None
    )
    client = logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    all_courses_list = list(response.context["all_courses"])
    course = next(c for c in all_courses_list if c.id == courses[0].id)
    assert course.listing_status == CourseListingStatus.IN_PROGRESS
    assert course.progress_percentage == 40


@pytest.mark.django_db
def test_all_courses_complete_has_complete_status(
    mock_site_context, courses, logged_in_client
):
    """A completed course has listing_status=COMPLETE."""
    user = UserFactory()
    UserCourseRegistrationFactory(user=user, collection=courses[0])
    CourseProgressFactory(
        user=user,
        course=courses[0],
        progress_percentage=100,
        completed_time=timezone.now(),
    )
    client = logged_in_client(user)

    response = client.get(reverse("student_interface:courses"))
    assert response.status_code == 200

    all_courses_list = list(response.context["all_courses"])
    course = next(c for c in all_courses_list if c.id == courses[0].id)
    assert course.listing_status == CourseListingStatus.COMPLETE
